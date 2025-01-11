from fsmate import StateDescriptor
from enum import Enum, auto
from random import randint


class GameState(Enum):
    Initial = auto()
    WelcomeMessage = auto()
    Difficulty = auto()
    Attempts = auto()
    GuessNumber = auto()
    GameOver = auto()
    ExitMessage = auto()


class Game:
    score: int = 0
    difficulty: int
    max_attempts: int

    state = StateDescriptor(GameState, GameState.Initial)

    welcome = state.transition(GameState.Initial, GameState.WelcomeMessage)

    configure = state.transition(GameState, GameState.Difficulty)
    select_attempts = state.transition(GameState.Difficulty, GameState.Attempts)

    restart_game = state.transition(GameState.GameOver, GameState.GuessNumber)
    start_game = state.transition(GameState.Attempts, GameState.GuessNumber)

    correct_number = state.transition(GameState.GuessNumber, GameState.GuessNumber)
    game_over = state.transition(GameState.GuessNumber, GameState.GameOver)

    exit = state.transition(GameState, GameState.ExitMessage)

    def run(self):
        self.welcome()

        while self.state != GameState.ExitMessage:
            self.process()

    @state.on_transition(exit)
    def print_exit_message(self, from_state, to_state):
        print(f'Total score: {self.score}')
        print('Bye!')

    @state.on_state_entered(GameState.GuessNumber)
    def guess_number(self, from_state, to_state):
        self.number = randint(1, self.difficulty)
        self.attempts_left = self.max_attempts
        print('I made a number. Can you guess it?')

    @state.on_transition(correct_number)
    def next_number(self, from_state, to_state):
        self.score += 1

    @state.on_transition(restart_game)
    def reset_score(self, from_state, to_state):
        print('Score was resetted')
        self.score = 0

    @state.dispatch
    def process(self) -> None:
        raise NotImplementedError()

    @state.on_state_entered(GameState.WelcomeMessage)
    def on_welcome_message_entered(self, from_state, to_state):
        print('Welcome to guess-the-number game!')
        print("Type 'q' to exit")
        print('Type anything to continue')

    @process.overload(GameState.WelcomeMessage)
    def process_welcome_message(self):
        res = input('>>> ')

        if res == 'q':
            self.exit()
        else:
            self.configure()

    @state.on_state_entered(GameState.Difficulty)
    def on_difficulty_entered(self, from_state, to_state):
        print('select difficulty (1-10)')
        print("Type 'q' to exit")

    @process.overload(GameState.Difficulty)
    def process_set_difficulty(self):
        res = input('>>> ')
        if res == 'q':
            self.exit()
            return
        try:
            res = int(res)
        except ValueError:
            return

        if res not in range(1, 101):
            return

        self.difficulty = res
        self.select_attempts()

    @state.on_state_entered(GameState.Attempts)
    def on_attemtps_entered(self, from_state, to_state):
        print('select attempts (1-10)')
        print("Type 'q' to exit")

    @process.overload(GameState.Attempts)
    def process_select_attempts(self):
        res = input('>>> ')
        if res == 'q':
            self.exit()
            return
        try:
            res = int(res)
        except ValueError:
            return
        if res not in range(1, 11):
            return
        self.max_attempts = res
        self.start_game()

    @process.overload(GameState.GuessNumber)
    def process_guess_number(self):
        if self.attempts_left <= 0:
            self.game_over()
            return
        print(f'Score: {self.score}')
        print(f'Attempts left: {self.attempts_left}')
        print('Type a number to guess')
        print("Type 'q' to exit")
        print("Type 'c' to change difficulty (score will be lost)")

        res = input('>>> ')
        if res == 'q':
            self.exit()
            return
        elif res == 'c':
            self.configure()
            return

        try:
            res = int(res)
        except ValueError:
            return

        if res > self.number:
            print('Your number in bigger')
            self.attempts_left -= 1
        elif res < self.number:
            print('Your number is lower')
            self.attempts_left -= 1
        else:
            print('Correct!')
            self.correct_number()

    @state.on_state_entered(GameState.GameOver)
    def on_game_over_entered(self, from_state, to_state):
        print('Game Over!')
        print(f'The number was {self.number}')
        print(f'Final score: {self.score}')
        print("Type 'r' to start again")
        print("Type 'c' to change difficulty")
        print("Type 'q' to exit")

    @process.overload(GameState.GameOver)
    def process_game_over(self):
        res = input('>>> ')
        if res == 'r':
            self.restart_game()
        elif res == 'c':
            self.configure()
        elif res == 'q':
            self.exit()


if __name__ == '__main__':
    game = Game()
    game.run()
