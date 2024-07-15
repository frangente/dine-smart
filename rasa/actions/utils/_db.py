# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

import uuid
from typing import Any, overload


class KeyValueStore:
    """In-memory key-value store."""

    def __init__(self) -> None:
        self._store = {}

    # ----------------------------------------------------------------------- #
    # Public methods
    # ----------------------------------------------------------------------- #

    def add(self, value: Any) -> str:
        """Adds a value to the store and returns the key.

        Args:
            value: The value to store.

        Returns:
            The key under which the value is stored.
        """
        while True:
            key = str(uuid.uuid4())
            if key not in self._store:
                break

        self._store[key] = value
        return key

    def set(self, key: str, value: Any) -> None:
        """Sets a value in the store.

        Args:
            key: The key under which to store the value.
            value: The value to store.
        """
        self._store[key] = value

    def update(self, key: str, value: Any) -> None:
        """Updates the value of an existing key.

        Args:
            key: The key of the value to update.
            value: The new value.

        Raises:
            KeyError: If the key does not exist.
        """
        if key not in self._store:
            raise KeyError(key)

        self._store[key] = value

    @overload
    def get(self, key: str) -> Any | None: ...

    @overload
    def get(self, key: str, default: Any) -> Any: ...

    def get(self, key: str, default: Any | None = None) -> Any | None:
        """Gets the value associated with the key.

        Args:
            key: The key of the value to get.
            default: The default value to return if the key does not exist.

        Returns:
            The value associated with the key, or the default value if the key
            does not exist.
        """
        return self._store.get(key, default)

    @overload
    def pop(self, key: str) -> Any | None: ...

    @overload
    def pop(self, key: str, default: Any) -> Any: ...

    def pop(self, key: str, default: Any | None = None) -> Any | None:
        """Pops the value associated with the key.

        Args:
            key: The key of the value to pop.
            default: The default value to return if the key does not exist.

        Returns:
            The value associated with the key, or the default value if the key
            does not exist.
        """
        return self._store.pop(key, default)

    # ----------------------------------------------------------------------- #
    # Magic methods
    # ----------------------------------------------------------------------- #

    def __getitem__(self, key: str) -> Any:
        if key not in self._store:
            raise KeyError(key)

        return self._store[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._store[key] = value

    def __delitem__(self, key: str) -> None:
        if key not in self._store:
            raise KeyError(key)

        del self._store[key]

    def __contains__(self, key: str) -> bool:
        return key in self._store


_store: KeyValueStore | None = None


def get_kv_store() -> KeyValueStore:
    """Returns the global key-value store."""
    global _store  # noqa: PLW0603

    if _store is None:
        _store = KeyValueStore()

    return _store
