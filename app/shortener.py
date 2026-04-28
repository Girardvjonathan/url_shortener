import random

CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE = len(CHARSET)  # 62

# Cap IDs to produce short codes of at most 3 characters.
# 62^3 = 238,328 possible values — sufficient for <100k URLs.
MAX_ID = BASE ** 3  # 238,328


def generate_unique_id() -> int:
    """Generate a random integer in [0, MAX_ID) for use as a primary key."""
    return random.randint(0, MAX_ID - 1)


def base62_encode(num: int) -> str:
    """Convert a non-negative integer to a base62 string.

    Examples:
        base62_encode(0)      -> "0"
        base62_encode(61)     -> "z"
        base62_encode(62)     -> "10"
        base62_encode(238327) -> "zzz"
    """
    if num < 0:
        raise ValueError("Cannot encode negative numbers")
    if num == 0:
        return CHARSET[0]

    result = []
    while num:
        num, rem = divmod(num, BASE)
        result.append(CHARSET[rem])
    return "".join(reversed(result))


def base62_decode(s: str) -> int:
    """Convert a base62 string back to an integer.

    Examples:
        base62_decode("0")   -> 0
        base62_decode("z")   -> 61
        base62_decode("10")  -> 62
        base62_decode("zzz") -> 238327
    """
    num = 0
    for char in s:
        idx = CHARSET.index(char)
        num = num * BASE + idx
    return num
