# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

"""Rasa custom actions for the chatbot."""

from ._misc import ActionGreet, ActionSessionStart
from ._search import (
    AskForLocation,
    AskForPlaceType,
    RankResults,
    Search,
    SetSearchParameters,
    ValidateSearchForm,
)
from ._search_history import (
    CheckNumberSelectedSearches,
    ClearSearchHistory,
    ConfirmDeleteSearches,
    DeleteSearches,
    SelectSearches,
    SetSelectedSearches,
    ShowSearchHistory,
    StartSearch,
)

__all__ = [
    # _misc
    "ActionGreet",
    "ActionSessionStart",
    # _search
    "AskForLocation",
    "AskForPlaceType",
    "RankResults",
    "Search",
    "SetSearchParameters",
    "ValidateSearchForm",
    # _search_history
    "CheckNumberSelectedSearches",
    "ClearSearchHistory",
    "ConfirmDeleteSearches",
    "DeleteSearches",
    "SelectSearches",
    "SetSelectedSearches",
    "ShowSearchHistory",
    "StartSearch",
]
