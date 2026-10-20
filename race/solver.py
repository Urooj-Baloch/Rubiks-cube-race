from collections import deque

from .cube import MOVES, SOLVED, apply_move, inverse_move

HALF_DEPTH = 3
EXACT_LIMIT = 2 * HALF_DEPTH

_table = None


def _build_table():
    table = {SOLVED: (0, None)}
    frontier = [SOLVED]
    for depth in range(1, HALF_DEPTH + 1):
        nxt = []
        for state in frontier:
            for m in MOVES:
                child = apply_move(state, m)
                if child not in table:
                    table[child] = (depth, inverse_move(m))
                    nxt.append(child)
        frontier = nxt
    return table


def table():
    global _table
    if _table is None:
        _table = _build_table()
    return _table


def _path_to_solved(state):
    t = table()
    path = []
    while state != SOLVED:
        _, back = t[state]
        path.append(back)
        state = apply_move(state, back)
    return path


def optimal_solution(state):
    t = table()
    if state in t:
        return _path_to_solved(state)
    seen = {state: []}
    layer = [state]
    best = None
    for depth in range(1, HALF_DEPTH + 1):
        nxt = []
        for s in layer:
            for m in MOVES:
                child = apply_move(s, m)
                if child in seen:
                    continue
                seen[child] = seen[s] + [m]
                nxt.append(child)
                if child in t:
                    total = depth + t[child][0]
                    if best is None or total < len(best):
                        best = seen[child] + _path_to_solved(child)
        layer = nxt
        if best is not None and len(best) <= depth + 1:
            break
    return best


def optimal_distance(state):
    sol = optimal_solution(state)
    return None if sol is None else len(sol)
