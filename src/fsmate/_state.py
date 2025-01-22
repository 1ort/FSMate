from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Collection
from enum import Enum
from typing import Any, Callable, Generic, NoReturn, Optional, TypeVar, Union, overload, Type
from typing_extensions import ParamSpec, Concatenate


class ImpossibleTransitionError(Exception):
    pass


class StateStorage(ABC):
    @abstractmethod
    def get_state(self, instance: object) -> Enum:
        raise NotImplementedError

    @abstractmethod
    def set_state(self, instance: object, state: Enum) -> None:
        raise NotImplementedError


class AttributeStateStorage(StateStorage):
    def __init__(self, attr_name: str) -> None:
        self._attr_name = attr_name

    def get_state(self, instance: object) -> Enum:
        return getattr(instance, self._attr_name)  # type: ignore[no-any-return]

    def set_state(self, instance: object, state: Enum) -> None:
        return setattr(instance, self._attr_name, state)


class ProxyStateStorage(StateStorage):
    def __init__(
        self, getter: Callable[[object], Enum], setter: Callable[[object, Enum], None]
    ) -> None:
        self._get_state = getter
        self._set_state = setter

    def get_state(self, instance: object) -> Enum:
        return self._get_state(instance)

    def set_state(self, instance: object, state: Enum) -> None:
        return self._set_state(instance, state)


_Instance = TypeVar('_Instance')
_TransitionCallable = Callable[[], None]


class StateTransition:
    """
    Retrieves state of the object and checks if the transition is possible.
    Updates state if so.
    Raises ImpossibleTransitionError otherwise
    """

    def __init__(self, source: Collection[Enum], dest: Enum, state_storage: StateStorage) -> None:
        self._source = source
        self._dest = dest
        self._storage = state_storage

        self._callbacks: list[Callable] = []

    @overload
    def __get__(self, instance: None, owner: Type[_Instance]) -> 'StateTransition':
        pass

    @overload
    def __get__(self, instance: _Instance, owner: Type[_Instance]) -> _TransitionCallable:
        pass

    def __get__(
        self, instance: Union[_Instance, None], owner: Type[_Instance]
    ) -> Union['StateTransition', _TransitionCallable]:
        if instance is None:
            return self

        def _transition() -> None:
            state = self._storage.get_state(instance)
            if state not in self._source:
                raise ImpossibleTransitionError()

            self._storage.set_state(instance, self._dest)
            for callback in self._callbacks:
                callback(instance, state, self._dest)

        return _transition

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(source={self._source!r}, dest={self._dest!r}, state_storage={self._storage!r})'

    def _register_callback(self, func: Callable) -> None:
        self._callbacks.append(func)


_MethodReturnType = TypeVar('_MethodReturnType')
_MethodArgs = ParamSpec('_MethodArgs')


class StateDispatcher(Generic[_Instance, _MethodArgs, _MethodReturnType]):
    def __init__(
        self,
        state_storage: StateStorage,
        all_states: type[Enum],
        fallback: Callable[Concatenate[_Instance, _MethodArgs], _MethodReturnType],
    ) -> None:
        self._all_states = all_states
        self._fallback = fallback
        self._state_storage = state_storage
        self._dispatch_table: dict[
            Enum, Callable[Concatenate[_Instance, _MethodArgs], _MethodReturnType]
        ] = {}

    def register(
        self, func: Callable[Concatenate[_Instance, _MethodArgs], _MethodReturnType], *states: Enum
    ) -> None:
        for state in states:
            if state not in self._all_states:
                raise ValueError('Target state not found', state)

            if state in self._dispatch_table:
                raise ValueError('Function is already overloaded for state', state)

            self._dispatch_table[state] = func

    def _get_dispatched_func(
        self, state: Enum
    ) -> Callable[Concatenate[_Instance, _MethodArgs], _MethodReturnType]:
        return self._dispatch_table.get(state, self._fallback)

    def dispatch(
        self, instance: _Instance, *args: _MethodArgs.args, **kwargs: _MethodArgs.kwargs
    ) -> _MethodReturnType:
        current_state = self._state_storage.get_state(instance)
        func = self._get_dispatched_func(current_state)
        print(func, args, kwargs, self._fallback)
        return func(instance, *args, **kwargs)


class StateDispatchedMethod(Generic[_Instance, _MethodArgs, _MethodReturnType]):
    def __init__(
        self, dispatcher: StateDispatcher[_Instance, _MethodArgs, _MethodReturnType]
    ) -> None:
        self._dispatcher = dispatcher

    @overload
    def __get__(self, instance: None, owner: Type[_Instance]) -> 'StateDispatchedMethod':
        pass

    @overload
    def __get__(
        self, instance: _Instance, owner: Type[_Instance]
    ) -> Callable[_MethodArgs, _MethodReturnType]:
        pass

    def __get__(
        self, instance: Union[None, _Instance], owner: Type[_Instance]
    ) -> Union[Callable[_MethodArgs, _MethodReturnType], 'StateDispatchedMethod']:
        if instance is None:
            return self

        def dispatched_method(
            *args: _MethodArgs.args, **kwargs: _MethodArgs.kwargs
        ) -> _MethodReturnType:
            return self._dispatcher.dispatch(instance, *args, **kwargs)

        return dispatched_method

    def overload(
        self, *states: Enum
    ) -> Callable[
        [Callable[Concatenate[_Instance, _MethodArgs], _MethodReturnType]],
        'StateDispatchedMethod[_Instance, _MethodArgs, _MethodReturnType]',
    ]:
        def deco(
            meth: Callable[Concatenate[_Instance, _MethodArgs], _MethodReturnType],
        ) -> 'StateDispatchedMethod[_Instance, _MethodArgs, _MethodReturnType]':
            self._dispatcher.register(meth, *states)
            return self

        return deco


class StateDescriptor:
    def __init__(
        self,
        states: type[Enum],
        initial_state: Optional[Enum] = None,
        state_storage: Optional[StateStorage] = None,
    ):
        if initial_state is None == state_storage is None:
            raise ValueError('Expected only one: initial_state or state_storage')

        self._all_states = states
        self._initial_state = initial_state
        self._state_storage = state_storage
        self._attr_name: Optional[str] = None
        self._transitions: list[StateTransition] = []
        self._enter_state_callbacks: dict[Enum, set[Callable[[object, Enum, Enum], Any]]] = (
            defaultdict(set)
        )
        self._exit_state_callbacks: dict[Enum, set[Callable[[object, Enum, Enum], Any]]] = (
            defaultdict(set)
        )

    def __set_name__(self, owner: type, attr_name: str) -> None:
        """
        Called once at the creation of owner class
        """
        self._attr_name = attr_name

    @overload
    def __get__(self, instance: None, owner: Type[_Instance]) -> 'StateDescriptor':
        pass

    @overload
    def __get__(self, instance: _Instance, owner: Type[_Instance]) -> Enum:
        pass

    def __get__(
        self, instance: Union[_Instance, None], owner: Type[_Instance]
    ) -> Union[Enum, 'StateDescriptor']:
        """
        Get current state from owner object
        """

        # return descriptor itself when called from class
        if instance is None:
            return self

        return self._get_state(instance)

    def _get_state(self, instance: object) -> Enum:
        if self._state_storage:
            return self._state_storage.get_state(instance)

        else:
            if self._attr_name is None:
                raise ValueError('Cannot get state from unitialized descriptor')

            return getattr(  # type: ignore[return-value]
                instance,
                '_' + self._attr_name,
                self._initial_state,
            )

    def _force_set_state(self, instance: object, state: Enum) -> None:
        current_state = self._get_state(instance)
        if self._state_storage:
            self._state_storage.set_state(instance, state)
        else:
            if self._attr_name is None:
                raise ValueError('Cannot set state via unitialized descriptor')
            setattr(
                instance,
                '_' + self._attr_name,
                state,
            )
        for callback in self._exit_state_callbacks[current_state]:
            callback(instance, current_state, state)
        for callback in self._enter_state_callbacks[state]:
            callback(instance, current_state, state)

    def __set__(self, instance: object, value: Any) -> NoReturn:
        """
        Forbit directly set state
        """
        raise AttributeError('Cannot change state directly. Use transitions')

    def transition(self, source: Union[Enum, Collection[Enum]], dest: Enum) -> StateTransition:
        """
        Create new transition callable
        """
        # check if value is correct Enum
        if dest not in self._all_states:
            raise ValueError('Destination state not found', dest)

        if not isinstance(source, Collection):
            source = [source]
        for source_state in source:
            if source_state not in self._all_states:
                raise ValueError('Source state not found', source)

        transition = StateTransition(
            source, dest, ProxyStateStorage(self._get_state, self._force_set_state)
        )
        self._transitions.append(transition)

        return transition

    def dispatch(
        self, method: Callable[Concatenate[_Instance, _MethodArgs], _MethodReturnType]
    ) -> StateDispatchedMethod[_Instance, _MethodArgs, _MethodReturnType]:
        dispatcher = StateDispatcher(
            ProxyStateStorage(self._get_state, self._force_set_state), self._all_states, method
        )
        dispatched_method = StateDispatchedMethod(dispatcher)
        return dispatched_method

    def on_transition(
        self, *transitions: StateTransition
    ) -> Callable[[Callable[[object, Enum, Enum], Any]], Callable[[object, Enum, Enum], Any]]:
        def wrapper(
            func: Callable[[object, Enum, Enum], Any],
        ) -> Callable[[object, Enum, Enum], Any]:
            for transition in transitions:
                transition._register_callback(func)
            return func

        if (
            len(transitions) == 1
            and callable(transitions[0])
            and not isinstance(transitions[0], StateTransition)
        ):
            func = transitions[0]
            transitions = self._transitions  # type: ignore[assignment]
            return wrapper(func)

        elif not transitions:
            transitions = self._transitions  # type: ignore[assignment]
        else:
            for transition in transitions:
                if transition not in self._transitions:
                    raise ValueError('Transition not found in current state machine', transition)

        return wrapper

    def on_state_exited(
        self, *states: Enum
    ) -> Callable[[Callable[[object, Enum, Enum], Any]], Callable[[object, Enum, Enum], Any]]:
        def wrapper(
            func: Callable[[object, Enum, Enum], Any],
        ) -> Callable[[object, Enum, Enum], Any]:
            for state in states:
                self._exit_state_callbacks[state].add(func)
            return func

        if len(states) == 1 and callable(states[0]) and not isinstance(states[0], Enum):
            func = states[0]
            states = tuple(self._all_states)
            return wrapper(func)
        else:
            for state in states:
                if state not in self._all_states:
                    raise ValueError('Target state not found', state)

        return wrapper

    def on_state_entered(
        self, *states: Enum
    ) -> Callable[[Callable[[object, Enum, Enum], Any]], Callable[[object, Enum, Enum], Any]]:
        def wrapper(
            func: Callable[[object, Enum, Enum], Any],
        ) -> Callable[[object, Enum, Enum], Any]:
            for state in states:
                self._enter_state_callbacks[state].add(func)
            return func

        if len(states) == 1 and callable(states[0]) and not isinstance(states[0], Enum):
            func = states[0]
            states = tuple(self._all_states)
            return wrapper(func)
        else:
            for state in states:
                if state not in self._all_states:
                    raise ValueError('Target state not found', state)

        return wrapper
