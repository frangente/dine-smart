# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

"""Rasa custom actions for the chatbot."""

from ._booking import (
    AskBookingAuthor,
    AskBookingDateTime,
    AskBookingPeopleCount,
    CancelBooking,
    CheckFutureBooking,
    CheckIsReservable,
    CreateBooking,
    SetBookingAuthor,
    SetBookingDateTime,
    SetBookingPeopleCount,
    ShowBookingDetails,
    StartBooking,
    StateNotReservable,
    SuggestBooking,
)
from ._booking_history import (
    ConfirmDeleteSelectedBookings,
    CountSelectedBookings,
    DeleteSelectedBookings,
    SetSelectedBookings,
    ShowSelectedBookings,
)
from ._info import RetrievePlaceInfo
from ._misc import Greet, OutOfScope, Restart, SessionStart
from ._results import CountSelectedResults, SetSelectedResults, ShowSelectedResults
from ._search import (
    AskSearchLocation,
    AskSearchPlaceType,
    CancelSearch,
    ChangeSearchRankBy,
    CreateSearch,
    Search,
    SearchParameters,
    SetSearchActivity,
    SetSearchLocation,
    SetSearchOpenNow,
    SetSearchPlaceType,
    SetSearchPriceRange,
    SetSearchQuality,
    ShowSearchParameters,
    StartSearch,
    ValidateSearchForm,
)
from ._search_history import (
    ConfirmDeleteSelectedSearches,
    CountSelectedSearches,
    DeleteSelectedSearches,
    SetSelectedSearches,
    ShowSelectedSearches,
)

__all__ = [
    # _booking
    "AskBookingAuthor",
    "AskBookingDateTime",
    "AskBookingPeopleCount",
    "CancelBooking",
    "CheckFutureBooking",
    "CheckIsReservable",
    "CreateBooking",
    "SetBookingAuthor",
    "SetBookingDateTime",
    "SetBookingPeopleCount",
    "ShowBookingDetails",
    "StartBooking",
    "StateNotReservable",
    "SuggestBooking",
    # _booking_history
    "ConfirmDeleteSelectedBookings",
    "CountSelectedBookings",
    "DeleteSelectedBookings",
    "SetSelectedBookings",
    "ShowSelectedBookings",
    # _info
    "RetrievePlaceInfo",
    # _misc
    "Greet",
    "OutOfScope",
    "Restart",
    "SessionStart",
    # _results
    "CountSelectedResults",
    "SetSelectedResults",
    "ShowSelectedResults",
    # _search
    "AskSearchLocation",
    "AskSearchPlaceType",
    "CancelSearch",
    "ChangeSearchRankBy",
    "CreateSearch",
    "Search",
    "SearchParameters",
    "SetSearchActivity",
    "SetSearchLocation",
    "SetSearchOpenNow",
    "SetSearchPlaceType",
    "SetSearchPriceRange",
    "SetSearchQuality",
    "ShowSearchParameters",
    "StartSearch",
    "ValidateSearchForm",
    # _search_history
    "ConfirmDeleteSelectedSearches",
    "CountSelectedSearches",
    "DeleteSelectedSearches",
    "SetSelectedSearches",
    "ShowSelectedSearches",
]
