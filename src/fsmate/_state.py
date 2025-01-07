from __future__ import annotations

from collections.abc import Collection
from enum import Enum
from typing import Any, Callable, Optional, Protocol, Union


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

    def get_state(self, instance: object):
        return getattr(instance, self._attr_name)

    def set_state(self, instance: object, state: Enum):
        return setattr(instance, self._attr_name, state)


class ProxyStateStorage:
    def __init__(self, getter, setter) -> None:
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

    def __get__(self, instance, objtype) -> Union['StateTransition', Callable[[], None]]:
        if instance is None:
            return self

        def _transition() -> None:
            state = self._storage.get_state(instance)
            if state in self._source:
                self._storage.set_state(instance, self._dest)
            else:
                raise ImpossibleTransitionError()

        return _transition


class StateDispatcher:
    def __init__(
        self, state_storage: StateStorage, all_states: type[Enum], fallback: Callable
    ) -> None:
        self._all_states = all_states
        self._fallback = fallback
        self._state_storage = state_storage
        self._dispatch_table = {}

    def register(self, func: Callable, *states: Enum):
        for state in states:
            if state not in self._all_states:
                raise ValueError('Target state not found', state)

            if state in self._dispatch_table:
                raise ValueError('Function is already overloaded for state', state)

            self._dispatch_table[state] = func

    def _dispatch(self, state: Enum) -> Callable:
        return self._dispatch_table.get(state, self._fallback)

    def dispatch(self, instance, *args, **kwargs) -> Any:
        current_state = self._state_storage.get_state(instance)
        func = self._dispatch(current_state)

        return func(*args, **kwargs)


class StateDispatchedMethod:
    def __init__(self, dispatcher: StateDispatcher) -> None:
        self._dispatcher = dispatcher

    def __get__(self, instance, objtype):
        if instance is None:
            return self

        def dispatched_method(*args, **kwargs):
            return self._dispatcher.dispatch(instance, instance, *args, **kwargs)

        return dispatched_method

    def overload(self, *states: Enum):
        def deco(meth):
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
        self._attr_name = None

    def __set_name__(self, owner: type, attr_name: str) -> None:
        """
        Called once at the creation of owner class
        """
        self._attr_name = attr_name

    def __get__(self, instance: object, objtype: Optional[type]):
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

            return getattr(
                instance,
                '_' + self._attr_name,
                self._initial_state,
            )

    def _force_set_state(self, instance: object, state: Enum) -> None:
        if self._state_storage:
            return self._state_storage.set_state(instance, state)
        else:
            if self._attr_name is None:
                raise ValueError('Cannot set state via unitialized descriptor')
            return setattr(
                instance,
                '_' + self._attr_name,
                state,
            )

    def __set__(self, instance: object, value: Any):
        """
        Forbit directly set state
        """
        raise AttributeError('Cannot change state directly. Use transitions')

    def transition(self, source: Union[Enum, Collection[Enum]], dest: Enum):
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

        return StateTransition(
            source, dest, ProxyStateStorage(self._get_state, self._force_set_state)
        )

    def dispatch(self, method):
        dispatcher = StateDispatcher(
            ProxyStateStorage(self._get_state, self._force_set_state), self._all_states, method
        )
        return StateDispatchedMethod(dispatcher)
