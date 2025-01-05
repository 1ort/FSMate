from collections.abc import Collection
from typing import Any, Optional, Union
from enum import Enum


class ImpossibleTransitionError(Exception):
    pass


class StateDescriptor:
    def __init__(self, states: type[Enum], initial_state: Enum, attr_name: Optional[str] = None):
        self._all_states = states
        self._initial_state = initial_state
        self._attr_name = attr_name
        self._has_owner = False

    def __set_name__(self, owner: type, attr_name: str) -> None:
        """
        Called once at the creation of owner class
        """
        # Without this check, infinite recursion is possible
        if attr_name == self._attr_name:
            raise ValueError(
                'The attr_name cannot be the same as the descriptor name. Use a different attr_name or remove this argument',
                attr_name,
            )
        self._attr_name = self._attr_name or '_' + attr_name
        self._has_owner = True

    def __get__(self, instance: object, objtype: Optional[type]):
        """
        Get current state from owner object
        """

        # return descriptor itself when called from class
        if instance is None:
            return self

        if self._attr_name is None:
            raise ValueError(
                'Cannot get a state of uninitialized state machine. Perhaps you forgot to set attr_name?'
            )

        return getattr(
            instance,
            self._attr_name,
            self._initial_state,
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

        def _update_state(instance):
            """
            Retrieves state of the object and checks if the transition is possible.
            Updates state if so.
            Raises ImpossibleTransitionError otherwise
            """
            state = self.__get__(instance, None)
            if state in source:
                setattr(instance, self._attr_name, dest)
            else:
                raise ImpossibleTransitionError()

        return _update_state
