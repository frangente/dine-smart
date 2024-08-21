# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

import uuid

from actions.records import BookingData, SearchData


class KeyValueStore:
    """In-memory key-value store."""

    def __init__(self) -> None:
        self._search_store: dict[str, SearchData] = {}
        self._booking_store: dict[str, BookingData] = {}

    # ----------------------------------------------------------------------- #
    # Public methods
    # ----------------------------------------------------------------------- #

    def add_booking(self, booking: BookingData) -> str:
        """Adds a booking to the store and returns the key.

        Args:
            booking: The booking to store.

        Returns:
            The key under which the booking is stored.
        """
        while True:
            key = str(uuid.uuid4())
            if key not in self._booking_store:
                break

        self._booking_store[key] = booking
        return key

    def add_search(self, search: SearchData) -> str:
        """Adds a search to the store and returns the key.

        Args:
            search: The search to store.

        Returns:
            The key under which the search is stored.
        """
        while True:
            key = str(uuid.uuid4())
            if key not in self._search_store:
                break

        self._search_store[key] = search
        return key

    def update_booking(self, key: str, booking: BookingData) -> None:
        """Updates the booking of an existing key.

        Args:
            key: The key of the booking to update.
            booking: The new booking.

        Raises:
            KeyError: If the key does not exist.
        """
        if key not in self._booking_store:
            raise KeyError(key)

        self._booking_store[key] = booking

    def update_search(self, key: str, search: SearchData) -> None:
        """Updates the search of an existing key.

        Args:
            key: The key of the search to update.
            search: The new search.

        Raises:
            KeyError: If the key does not exist.
        """
        if key not in self._search_store:
            raise KeyError(key)

        self._search_store[key] = search

    def get_booking(self, key: str) -> BookingData:
        """Returns the booking associated with the key.

        Args:
            key: The key of the booking to retrieve.

        Returns:
            The booking associated with the key.

        Raises:
            KeyError: If the key does not exist.
        """
        return self._booking_store[key]

    def get_search(self, key: str) -> SearchData:
        """Returns the search associated with the key.

        Args:
            key: The key of the search to retrieve.

        Returns:
            The search associated with the key.

        Raises:
            KeyError: If the key does not exist.
        """
        return self._search_store[key]

    def delete_booking(self, key: str) -> None:
        """Deletes the booking associated with the key.

        Args:
            key: The key of the booking to delete.

        Raises:
            KeyError: If the key does not exist.
        """
        del self._booking_store[key]

    def delete_search(self, key: str) -> None:
        """Deletes the search associated with the key.

        Args:
            key: The key of the search to delete.

        Raises:
            KeyError: If the key does not exist.
        """
        del self._search_store[key]


_store: KeyValueStore | None = None


def get_kv_store() -> KeyValueStore:
    """Returns the global key-value store."""
    global _store  # noqa: PLW0603

    if _store is None:
        _store = KeyValueStore()

    return _store
