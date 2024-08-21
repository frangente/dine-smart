# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

"""Module defining dataclasses for the chatbot."""

from ._booking import BookingData, BookingParameters
from ._search import SearchData, SearchParameters

__all__ = [
    # _booking
    "BookingData",
    "BookingParameters",
    # _search
    "SearchData",
    "SearchParameters",
]
