# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

"""Utilities for Google Maps."""

from gcp import maps

_client: maps.Client | None = None


def get_maps_client() -> maps.Client:
    """Returns the Google Maps client."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = maps.Client()
    return _client
