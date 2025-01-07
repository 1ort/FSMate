from enum import Enum, auto

from fsmate import StateDescriptor
from fsmate._state import ImpossibleTransitionError


class State(Enum):
    Username = auto()
    Password = auto()
    AccessGranted = auto()
    AccessDenied = auto()


class SigninPage:
    state = StateDescriptor(
        State,
        initial_state=State.Username,
    )

    # username is valid
    confirm_username = state.transition(
        State.Username,
        State.Password,
    )

    # username not found
    reject_username = state.transition(
        State.Username,
        State.AccessDenied,
    )

    # authenticated
    confirm_password = state.transition(
        State.Password,
        State.AccessGranted,
    )

    # wrong password - show error screen
    reject_password = state.transition(
        State.Password,
        State.AccessDenied,
    )

    # try again
    retry = state.transition(
        State.AccessDenied,
        State.Username,
    )


page = SigninPage()
print(page.state)  # State.Username

# Enter wrong username
page.reject_username()
print(page.state)  # State.AccessDenied

page.retry()

print(page.state)  # State.Username
page.confirm_username()
page.confirm_password()
print(page.state)  # State.AccessGranted

try:
    page.retry()
except ImpossibleTransitionError as error:
    print(error)

try:
    page.state = State.Username
except AttributeError as error:
    print(error)
