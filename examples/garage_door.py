from enum import Enum, auto
from typing import Any
from fsmate import StateDescriptor
from dataclasses import dataclass


class DoorState(Enum):
    closed = auto()
    opening = auto()
    opened = auto()
    closing = auto()


@dataclass
class GarageDoor:
    motor: Any
    alarm: Any

    state = StateDescriptor(DoorState, DoorState.closed)

    start_opening = state.transition(DoorState.closed, DoorState.opening)
    finish_opening = state.transition(DoorState.opening, DoorState.opened)
    start_closing = state.transition(DoorState.opened, DoorState.closing)
    finish_closing = state.transition(DoorState.closing, DoorState.closed)

    @state.on_transition(start_opening)
    def on_start_opening(self, _source, _dest):
        self.motor.up()

    @state.on_transition(finish_opening)
    def on_finish_opening(self, _source, _dest):
        self.motor.stop()

    @state.on_transition(start_closing)
    def on_start_closing(self, _source, _dest):
        self.motor.down()
        self.alarm.beep()

    @state.on_transition(finish_closing)
    def on_finish_closing(self, _source, _dest):
        self.motor.stop()

    @state.dispatch
    def push_button(self):
        self.alarm.beep()  # default behavior

    @push_button.overload(DoorState.closed)
    def push_button_closed(self):
        self.start_opening()

    @push_button.overload(DoorState.opened)
    def push_button_opened(self):
        self.start_closing()


class Alarm:
    def beep(self):
        print('beep')


class Motor:
    def up(self):
        print('motor up')

    def down(self):
        print('motor down')

    def stop(self):
        print('motor stop')


door = GarageDoor(Motor(), Alarm())
door.push_button()  # motor up
door.finish_opening()  # motor stop

door.push_button()  # motor down & beep

door.finish_closing()  # motor stop

door.push_button()  # motor up
door.push_button()  # beep
door.push_button()  # beep
