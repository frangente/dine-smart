# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Iterable
from typing import Any, TypeVar

import serde


def join(
    args: Iterable[str | None],
    /,
    sep: str = " ",
    last_sep: str | None = None,
) -> str:
    """Joins strings using a separator.

    Different from the built-in `str.join` method, this function filters out `None`
    values before joining the strings.

    Args:
        args: The strings to join.
        sep: The separator to use between strings.
        last_sep: The separator to use before the last string. If `None`, the last
            separator is not used.

    Returns:
        The joined string.
    """
    args = [arg for arg in args if arg is not None]
    if len(args) == 0:
        return ""
    if len(args) == 1:
        return args[0]

    if last_sep is None:
        return sep.join(args)

    return f"{sep.join(args[:-1])} {last_sep} {args[-1]}"


def serialize(x: Any, /) -> dict[str, Any]:
    """Serializes an object to a dictionary."""
    result = serde.to_dict(x)
    result = {k: v for k, v in result.items() if v is not None}
    return result


def serialize_iterable(x: Iterable[Any], /) -> list[dict[str, Any]]:
    """Serializes a list of objects to a list of dictionaries."""
    return [serialize(item) for item in x]


_T = TypeVar("_T")


def deserialize(cls: type[_T], x: dict[str, Any], /) -> _T:
    """Deserializes an object from a dictionary."""
    return serde.from_dict(cls, x)


def deserialize_iterable(cls: type[_T], x: list[dict[str, Any]], /) -> list[_T]:
    """Deserializes a list of objects from a list of dictionaries."""
    return [deserialize(cls, item) for item in x]
