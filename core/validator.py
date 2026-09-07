from core.moves import legal_moves
from core.notation import slide_to_move
from core.simulator import apply_move, is_goal
from core.state import initial_state


class InvalidSolution(ValueError):
    pass


def validate_solution(level, slides):
    state = initial_state(level)
    for number, slide in enumerate(slides, 1):
        try:
            move = slide_to_move(level, slide)
        except (KeyError, ValueError) as error:
            raise InvalidSolution(f"move {number} ({slide}): {error}") from error
        if move not in set(legal_moves(level, state)):
            raise InvalidSolution(f"move {number} ({slide}) is not a legal slide from the current state")
        state = apply_move(level, state, move)
    if not is_goal(level, state):
        raise InvalidSolution(f"after {len(slides)} moves the level is not solved")
    return state
