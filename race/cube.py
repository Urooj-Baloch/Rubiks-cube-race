import random

FACES = "URFDLB"
SOLVED = "".join(f * 9 for f in FACES)
SUFFIXES = ("", "'", "2")
MOVES = tuple(f + s for f in FACES for s in SUFFIXES)
OPPOSITE = {"U": "D", "D": "U", "R": "L", "L": "R", "F": "B", "B": "F"}
NORMALS = {
    "U": (0, 1, 0),
    "R": (1, 0, 0),
    "F": (0, 0, 1),
    "D": (0, -1, 0),
    "L": (-1, 0, 0),
    "B": (0, 0, -1),
}


def _stickers():
    out = []
    for r in range(3):
        for c in range(3):
            out.append(((c - 1, 1, r - 1), (0, 1, 0)))
    for r in range(3):
        for c in range(3):
            out.append(((1, 1 - r, 1 - c), (1, 0, 0)))
    for r in range(3):
        for c in range(3):
            out.append(((c - 1, 1 - r, 1), (0, 0, 1)))
    for r in range(3):
        for c in range(3):
            out.append(((c - 1, -1, 1 - r), (0, -1, 0)))
    for r in range(3):
        for c in range(3):
            out.append(((-1, 1 - r, c - 1), (-1, 0, 0)))
    for r in range(3):
        for c in range(3):
            out.append(((1 - c, 1 - r, -1), (0, 0, -1)))
    return out


_STICKERS = _stickers()
_INDEX = {s: i for i, s in enumerate(_STICKERS)}


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _rotate_cw(v, n):
    cr = _cross(n, v)
    d = _dot(n, v)
    return (-cr[0] + n[0] * d, -cr[1] + n[1] * d, -cr[2] + n[2] * d)


def _quarter_permutation(face):
    n = NORMALS[face]
    perm = list(range(54))
    for idx, (pos, nor) in enumerate(_STICKERS):
        if _dot(pos, n) == 1:
            dest = _INDEX[(_rotate_cw(pos, n), _rotate_cw(nor, n))]
            perm[dest] = idx
    return perm


def _compose(p, q):
    return [p[q[i]] for i in range(54)]


def _build_permutations():
    perms = {}
    for face in FACES:
        q = _quarter_permutation(face)
        q2 = _compose(q, q)
        q3 = _compose(q, q2)
        perms[face] = tuple(q)
        perms[face + "2"] = tuple(q2)
        perms[face + "'"] = tuple(q3)
    return perms


PERMUTATIONS = _build_permutations()


def apply_move(state, move):
    if move not in PERMUTATIONS:
        raise ValueError("invalid move: %r" % (move,))
    p = PERMUTATIONS[move]
    return "".join([state[i] for i in p])


def apply_moves(state, moves):
    for m in moves:
        state = apply_move(state, m)
    return state


def inverse_move(move):
    if move.endswith("'"):
        return move[0]
    if move.endswith("2"):
        return move
    return move + "'"


def inverse_sequence(moves):
    return [inverse_move(m) for m in reversed(moves)]


def is_solved(state):
    return all(len(set(state[i * 9:(i + 1) * 9])) == 1 for i in range(6))


def is_valid_state(state):
    if not isinstance(state, str) or len(state) != 54:
        return False
    return all(state.count(f) == 9 for f in FACES)


def random_scramble(length, rng=None):
    rng = rng or random.Random()
    while True:
        seq = []
        while len(seq) < length:
            face = rng.choice(FACES)
            if seq and seq[-1][0] == face:
                continue
            if len(seq) >= 2 and seq[-2][0] == face and OPPOSITE[seq[-1][0]] == face:
                continue
            if len(seq) >= 2 and seq[-2][0] == face and seq[-1][0] == OPPOSITE[face]:
                continue
            seq.append(face + rng.choice(SUFFIXES))
        if not is_solved(apply_moves(SOLVED, seq)):
            return seq


def face_rows(state):
    names = {"U": "Up", "R": "Right", "F": "Front", "D": "Down", "L": "Left", "B": "Back"}
    out = {}
    for i, f in enumerate(FACES):
        chunk = state[i * 9:(i + 1) * 9]
        out[names[f]] = [chunk[0:3], chunk[3:6], chunk[6:9]]
    return out


MOVE_DESCRIPTIONS = {}
_FACE_NAMES = {"U": "upper", "R": "right", "F": "front", "D": "down", "L": "left", "B": "back"}
for _f in FACES:
    MOVE_DESCRIPTIONS[_f] = "Turn the %s face clockwise by 90 degrees" % _FACE_NAMES[_f]
    MOVE_DESCRIPTIONS[_f + "'"] = "Turn the %s face counterclockwise by 90 degrees" % _FACE_NAMES[_f]
    MOVE_DESCRIPTIONS[_f + "2"] = "Turn the %s face by 180 degrees" % _FACE_NAMES[_f]
