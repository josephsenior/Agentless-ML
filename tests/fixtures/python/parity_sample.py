"""Module documentation intentionally omitted by the skeleton."""

from __future__ import annotations

LIMIT = 3
VALUES = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
}


def decorated(flag: bool = True) -> int:
    """A top-level synchronous function."""
    if flag:
        return LIMIT
    return 0


async def fetch(name: str) -> str:
    return name


class Worker:
    """Class documentation is removed from the skeleton."""

    def __init__(self, value: int):
        self.value = value

    async def async_run(self) -> int:
        return self.value

    def run(self) -> int:
        def nested() -> int:
            return self.value

        return nested()


def run() -> str:
    return "top-level name collision"
