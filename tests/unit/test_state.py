import unittest
from enum import Enum, auto

from fsmate import StateDescriptor, ImpossibleTransitionError
from fsmate._state import AttributeStateStorage


class State(Enum):
    A = auto()
    B = auto()
    C = auto()


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
    def setUp(self) -> None:
        class WrongState(Enum):
            D = auto()
            E = auto()
            F = auto()

        self.wrong_state = WrongState

    def test_destination_state_not_found(self):
        with self.assertRaisesRegex(ValueError, 'Destination state not found'):

            class _:
                state = StateDescriptor(State, State.A)
                to_d = state.transition(State.A, self.wrong_state.D)

    def test_source_state_not_found(self):
        with self.assertRaisesRegex(ValueError, 'Source state not found'):

            class _:
                state = StateDescriptor(State, State.A)
                from_d_to_a = state.transition(self.wrong_state.D, State.A)

    def test_one_of_sources_not_found(self):
        with self.assertRaisesRegex(ValueError, 'Source state not found'):

            class _:
                state = StateDescriptor(State, State.A)
                from_b_or_d_to_a = state.transition([State.B, self.wrong_state.D], State.A)


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
