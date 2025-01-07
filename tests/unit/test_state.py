import unittest
from enum import Enum, auto

from fsmate import ImpossibleTransitionError, StateDescriptor
from fsmate._state import AttributeStateStorage, StateDispatcher


class State(Enum):
    A = auto()
    B = auto()
    C = auto()


class WrongState(Enum):
    D = auto()
    E = auto()
    F = auto()


class TestStateAttribute(unittest.TestCase):
    def setUp(self) -> None:
        class Stub:
            state = StateDescriptor(State, State.A)

        self.obj = Stub()

    def test_initital_state(self):
        self.assertEqual(self.obj.state, State.A)

    def test_forbid_state_direct_change(self):
        with self.assertRaisesRegex(
            AttributeError, 'Cannot change state directly. Use transitions'
        ):
            self.obj.state = State.B

    def test_default_attribute_change(self):
        with self.assertRaises(AttributeError):
            self.obj._state

        self.obj._state = State.B
        self.assertEqual(self.obj.state, State.B)

    def test_custom_atribute_change(self):
        class Stub:
            state_attribute: State = State.A
            state = StateDescriptor(State, state_storage=AttributeStateStorage('state_attribute'))

        obj = Stub()

        self.assertEqual(obj.state, State.A)

        obj.state_attribute = State.B
        self.assertEqual(obj.state, State.B)


class TestDeclareTransitions(unittest.TestCase):
    def test_destination_state_not_found(self):
        with self.assertRaisesRegex(ValueError, 'Destination state not found'):

            class _:
                state = StateDescriptor(State, State.A)
                to_d = state.transition(State.A, WrongState.D)

    def test_source_state_not_found(self):
        with self.assertRaisesRegex(ValueError, 'Source state not found'):

            class _:
                state = StateDescriptor(State, State.A)
                from_d_to_a = state.transition(WrongState.D, State.A)

    def test_one_of_sources_not_found(self):
        with self.assertRaisesRegex(ValueError, 'Source state not found'):

            class _:
                state = StateDescriptor(State, State.A)
                from_b_or_d_to_a = state.transition([State.B, WrongState.D], State.A)


class TestTransitions(unittest.TestCase):
    def setUp(self) -> None:
        class Stub:
            state = StateDescriptor(State, State.A)

            to_b = state.transition(State.A, State.B)
            to_c = state.transition(State.B, State.C)
            to_a_from_c = state.transition(State.C, State.A)
            to_b_from_a_or_c = state.transition([State.A, State.C], State.B)

        self.obj = Stub()

    def test_valid_transition(self):
        self.assertEqual(self.obj.state, State.A)
        self.obj.to_b()
        self.assertEqual(self.obj.state, State.B)

        self.obj.to_c()
        self.assertEqual(self.obj.state, State.C)

        self.obj.to_a_from_c()
        self.assertEqual(self.obj.state, State.A)

        self.obj.to_b_from_a_or_c()
        self.assertEqual(self.obj.state, State.B)

    def test_invalid_transition(self):
        with self.assertRaises(ImpossibleTransitionError):
            self.obj.to_c()

    def test_multiple_sources(self):
        self.obj.to_b_from_a_or_c()
        self.assertEqual(self.obj.state, State.B)

        self.obj._state = State.C
        self.obj.to_b_from_a_or_c()
        self.assertEqual(self.obj.state, State.B)

        self.obj._state = State.B
        with self.assertRaises(ImpossibleTransitionError):
            self.obj.to_b_from_a_or_c()


class TestMethodOverload(unittest.TestCase):
    def test_state_dispatcher(self):
        class StubStateStorage:
            def get_state(self, instance):
                return self.state

            def set_state(self, instance, state):
                self.state = state

        def fallback(x):
            return x

        def b_func(x):
            return x * 2

        storage = StubStateStorage()
        storage.state = State.A
        dispatcher = StateDispatcher(storage, State, fallback)
        dispatcher.register(b_func, State.B)

        self.assertEqual(dispatcher.dispatch(None, 10), 10)
        storage.set_state(None, State.B)
        self.assertEqual(dispatcher.dispatch(None, 10), 20)
        storage.set_state(None, State.C)
        self.assertEqual(dispatcher.dispatch(None, 10), 10)

        with self.assertRaisesRegex(ValueError, 'Target state not found'):
            dispatcher.register(lambda x: x, WrongState.D)

        with self.assertRaisesRegex(ValueError, 'Function is already overloaded for state'):
            dispatcher.register(lambda x: x, State.B)

    def test_overload(self):
        class Stub:
            state = StateDescriptor(State, State.A)

            to_b = state.transition(State.A, State.B)
            to_c = state.transition(State.B, State.C)

            @state.dispatch
            def foo(self):
                return 0

            @foo.overload(State.B)
            def _(self):
                return 1

        obj = Stub()

        self.assertEqual(obj.foo(), 0)

        obj.to_b()
        self.assertEqual(obj.foo(), 1)

        obj.to_c()
        self.assertEqual(obj.foo(), 0)
