import random

from race.cube import (
    FACES,
    MOVES,
    SOLVED,
    apply_move,
    apply_moves,
    inverse_move,
    inverse_sequence,
    is_solved,
    is_valid_state,
    random_scramble,
)
from race.solver import optimal_distance, optimal_solution


def test_solved_state_is_solved():
    assert is_solved(SOLVED)
    assert is_valid_state(SOLVED)


def test_u_move_matches_reference_facelets():
    s = apply_move(SOLVED, "U")
    assert s[0:9] == "UUUUUUUUU"
    assert s[9:12] == "BBB" and s[12:18] == "RRRRRR"
    assert s[18:21] == "RRR" and s[21:27] == "FFFFFF"
    assert s[27:36] == "DDDDDDDDD"
    assert s[36:39] == "FFF" and s[39:45] == "LLLLLL"
    assert s[45:48] == "LLL" and s[48:54] == "BBBBBB"


def test_every_move_order_and_inverse():
    for m in MOVES:
        s = apply_move(SOLVED, m)
        assert is_valid_state(s)
        assert not is_solved(s)
        assert apply_move(s, inverse_move(m)) == SOLVED


def test_four_quarter_turns_identity():
    for f in FACES:
        s = SOLVED
        for _ in range(4):
            s = apply_move(s, f)
        assert s == SOLVED


def test_half_turn_equals_two_quarters():
    for f in FACES:
        assert apply_move(SOLVED, f + "2") == apply_moves(SOLVED, [f, f])


def test_sexy_move_has_order_six():
    s = SOLVED
    for _ in range(6):
        s = apply_moves(s, ["R", "U", "R'", "U'"])
    assert s == SOLVED


def test_scramble_and_inverse_roundtrip():
    rng = random.Random(7)
    for n in (3, 5, 18):
        seq = random_scramble(n, rng)
        assert len(seq) == n
        assert apply_moves(apply_moves(SOLVED, seq), inverse_sequence(seq)) == SOLVED


def test_optimal_solver_exact_on_known_cases():
    assert optimal_distance(SOLVED) == 0
    assert optimal_distance(apply_move(SOLVED, "R2")) == 1
    assert optimal_distance(apply_moves(SOLVED, ["R", "U"])) == 2
    assert optimal_distance(apply_moves(SOLVED, ["R", "U", "F"])) == 3


def test_optimal_solver_solutions_solve_and_do_not_exceed_scramble():
    rng = random.Random(11)
    for n in (4, 5, 6):
        for _ in range(4):
            seq = random_scramble(n, rng)
            state = apply_moves(SOLVED, seq)
            sol = optimal_solution(state)
            assert sol is not None
            assert len(sol) <= n
            assert is_solved(apply_moves(state, sol))
