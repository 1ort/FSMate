from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from enum import Enum
from typing import Any, Callable, Generic, NoReturn, Optional, Protocol, TypeVar, Union
from typing_extensions import ParamSpec


class ImpossibleTransitionError(Exception):
    pass


class StateStorage(Protocol):
    def get_state(self, instance: object) -> Enum:
        raise NotImplementedError

    def set_state(self, instance: object, state: Enum) -> None:
        raise NotImplementedError


class AttributeStateStorage:
    def __init__(self, attr_name: str) -> None:
        self._attr_name = attr_name

    def get_state(self, instance: object) -> Enum:
        return getattr(instance, self._attr_name)  # type: ignore[no-any-return]

    def set_state(self, instance: object, state: Enum) -> None:
        return setattr(instance, self._attr_name, state)


class ProxyStateStorage:
    def __init__(
        self, getter: Callable[[object], Enum], setter: Callable[[object, Enum], None]
    ) -> None:
        self.get_state = getter
        self.set_state = setter


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

    def __get__(
        self, instance: object, objtype: type
    ) -> Union['StateTransition', Callable[[], None]]:
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

    def __call__(self) -> None:
        pass

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(source={self._source!r}, dest={self._dest!r}, state_storage={self._storage!r})'

    def _register_callback(self, func: Callable) -> None:
        self._callbacks.append(func)


T = TypeVar('T')
P = ParamSpec('P')


class StateDispatcher(Generic[P, T]):
    def __init__(
        self, state_storage: StateStorage, all_states: type[Enum], fallback: Callable[P, T]
    ) -> None:
        self._all_states = all_states
        self._fallback = fallback
        self._state_storage = state_storage
        self._dispatch_table: dict[Enum, Callable[P, T]] = {}

    def register(self, func: Callable[P, T], *states: Enum) -> None:
        for state in states:
            if state not in self._all_states:
                raise ValueError('Target state not found', state)

            if state in self._dispatch_table:
                raise ValueError('Function is already overloaded for state', state)

            self._dispatch_table[state] = func

    def _dispatch(self, state: Enum) -> Callable[P, T]:
        return self._dispatch_table.get(state, self._fallback)

    def dispatch(self, instance: object, *args: P.args, **kwargs: P.kwargs) -> T:
        current_state = self._state_storage.get_state(instance)
        func = self._dispatch(current_state)

        return func(*args, **kwargs)


class StateDispatchedMethod(Generic[P, T]):
    def __init__(self, dispatcher: StateDispatcher[P, T]) -> None:
        self._dispatcher = dispatcher

    def __get__(self, instance: object, objtype: type) -> Callable[P, T]:
        if instance is None:
            return self  # type: ignore[return-value]

        def dispatched_method(*args: P.args, **kwargs: P.kwargs) -> T:
            return self._dispatcher.dispatch(instance, instance, *args, **kwargs)  # type: ignore[arg-type]

        return dispatched_method

    def overload(self, *states: Enum) -> Callable[[Callable[P, T]], 'StateDispatchedMethod[P, T]']:
        def deco(meth: Callable[P, T]) -> 'StateDispatchedMethod[P, T]':
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

    def __get__(self, instance: object, objtype: Optional[type]) -> Enum:
        """
        Get current state from owner object
        """

        # return descriptor itself when called from class
        if instance is None:
            return self  # type: ignore[return-value]

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

    def dispatch(self, method: Callable[P, T]) -> StateDispatchedMethod[P, T]:
        dispatcher = StateDispatcher(
            ProxyStateStorage(self._get_state, self._force_set_state), self._all_states, method
        )
        dispatched_method = StateDispatchedMethod(dispatcher)
        return dispatched_method

    def on_transition(
        self, *transitions: StateTransition
    ) -> Callable[[Callable[[object, Enum, Enum], Any]], Callable[[object, Enum, Enum], Any]]:
        if transitions:
            for transition in transitions:
                if transition not in self._transitions:
                    raise ValueError('Transition not found in current state machine', transition)
        else:
            transitions = self._transitions  # type: ignore[assignment]

        def wrapper(
            func: Callable[[object, Enum, Enum], Any],
        ) -> Callable[[object, Enum, Enum], Any]:
            for transition in transitions:
                transition._register_callback(func)
            return func

        return wrapper

    def on_state_exited(
        self, *states: Enum
    ) -> Callable[[Callable[[object, Enum, Enum], Any]], Callable[[object, Enum, Enum], Any]]:
        if states:
            for state in states:
                if state not in self._all_states:
                    raise ValueError('Target state not found', state)
        else:
            states = tuple(self._all_states)

        def wrapper(
            func: Callable[[object, Enum, Enum], Any],
        ) -> Callable[[object, Enum, Enum], Any]:
            for state in states:
                self._exit_state_callbacks[state].add(func)
            return func

        return wrapper

    def on_state_entered(
        self, *states: Enum
    ) -> Callable[[Callable[[object, Enum, Enum], Any]], Callable[[object, Enum, Enum], Any]]:
        if states:
            for state in states:
                if state not in self._all_states:
                    raise ValueError('Target state not found', state)
        else:
            states = tuple(self._all_states)

        def wrapper(
            func: Callable[[object, Enum, Enum], Any],
        ) -> Callable[[object, Enum, Enum], Any]:
            for state in states:
                self._enter_state_callbacks[state].add(func)
            return func

        return wrapper
