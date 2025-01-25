from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Collection
from enum import Enum


class ImpossibleTransitionError(Exception):
    pass


class StateStorage(ABC):
    @abstractmethod
    def get_state(self, instance):
        raise NotImplementedError

    @abstractmethod
    def set_state(self, instance, state):
        raise NotImplementedError


class AttributeStateStorage(StateStorage):
    def __init__(self, attr_name):
        self._attr_name = attr_name

    def get_state(self, instance):
        return getattr(instance, self._attr_name)

    def set_state(self, instance, state):
        return setattr(instance, self._attr_name, state)


class ProxyStateStorage(StateStorage):
    def __init__(self, getter, setter):
        self._get_state = getter
        self._set_state = setter

    def get_state(self, instance):
        return self._get_state(instance)

    def set_state(self, instance, state):
        return self._set_state(instance, state)


class StateTransition:
    def __init__(self, source, dest, state_storage):
        self._source = source
        self._dest = dest
        self._storage = state_storage
        self._callbacks = []

    def __get__(self, instance, owner):
        if instance is None:
            return self

        def _transition():
            state = self._storage.get_state(instance)
            if state not in self._source:
                raise ImpossibleTransitionError()

            self._storage.set_state(instance, self._dest)
            for callback in self._callbacks:
                callback(instance, state, self._dest)

        return _transition

    def __repr__(self):
        return f'{self.__class__.__name__}(source={self._source!r}, dest={self._dest!r}, state_storage={self._storage!r})'

    def _register_callback(self, func):
        self._callbacks.append(func)


class StateDispatcher:
    def __init__(self, state_storage, all_states, fallback):
        self._all_states = all_states
        self._fallback = fallback
        self._state_storage = state_storage
        self._dispatch_table = {}

    def register(self, func, *states):
        for state in states:
            if state not in self._all_states:
                raise ValueError('Target state not found', state)

            if state in self._dispatch_table:
                raise ValueError('Function is already overloaded for state', state)

            self._dispatch_table[state] = func

    def _get_dispatched_func(self, state):
        return self._dispatch_table.get(state, self._fallback)

    def dispatch(self, instance, *args, **kwargs):
        current_state = self._state_storage.get_state(instance)
        func = self._get_dispatched_func(current_state)
        return func(instance, *args, **kwargs)


class StateDispatchedMethod:
    def __init__(self, dispatcher):
        self._dispatcher = dispatcher

    def __get__(self, instance, owner):
        if instance is None:
            return self

        def dispatched_method(*args, **kwargs):
            return self._dispatcher.dispatch(instance, *args, **kwargs)

        return dispatched_method

    def overload(self, *states):
        def deco(meth):
            self._dispatcher.register(meth, *states)
            return self

        return deco


class StateDescriptor:
    def __init__(self, states, initial_state=None, state_storage=None):
        if initial_state is None == state_storage is None:
            raise ValueError('Expected only one: initial_state or state_storage')

        self._all_states = states
        self._initial_state = initial_state
        self._state_storage = state_storage
        self._attr_name = None
        self._transitions = []
        self._enter_state_callbacks = defaultdict(set)
        self._exit_state_callbacks = defaultdict(set)

    def __set_name__(self, owner, attr_name):
        self._attr_name = attr_name

    def __get__(self, instance, owner):
        if instance is None:
            return self

        return self._get_state(instance)

    def _get_state(self, instance):
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

    def _force_set_state(self, instance, state):
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

    def __set__(self, instance, value):
        raise AttributeError('Cannot change state directly. Use transitions')

    def transition(self, source, dest):
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

    def dispatch(self, method):
        dispatcher = StateDispatcher(
            ProxyStateStorage(self._get_state, self._force_set_state), self._all_states, method
        )
        dispatched_method = StateDispatchedMethod(dispatcher)
        return dispatched_method

    def on_transition(self, *transitions):
        def wrapper(func):
            for transition in transitions:
                transition._register_callback(func)
            return func

        if (
            len(transitions) == 1
            and callable(transitions[0])
            and not isinstance(transitions[0], StateTransition)
        ):
            func = transitions[0]
            transitions = self._transitions
            return wrapper(func)

        elif not transitions:
            transitions = self._transitions
        else:
            for transition in transitions:
                if transition not in self._transitions:
                    raise ValueError('Transition not found in current state machine', transition)

        return wrapper

    def on_state_exited(self, *states):
        def wrapper(func):
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

    def on_state_entered(self, *states):
        def wrapper(func):
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
