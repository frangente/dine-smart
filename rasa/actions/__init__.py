# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

"""Rasa custom actions for the chatbot."""

from ._guards import SearchHistoryGuard, SelectedSearchesGuard
from ._info import RetrievePlaceInfo
from ._misc import Greet, OutOfScope, Restart, SessionStart
from ._search import (
    AskForSearchParameters,
    CheckSearchParameters,
    RankResults,
    Search,
    SetSearchParameters,
    ShowSearchParameters,
    ShowSelectedResults,
)
from ._search_history import (
    AskSearchDeletion,
    ClearSearchHistory,
    DeleteSearches,
    SetSelectedSearches,
    ShowSearchHistory,
    ShowSelectedSearches,
    StartSearch,
)

__all__ = [
    # _guards
    "SearchHistoryGuard",
    "SelectedSearchesGuard",
    # _info
    "RetrievePlaceInfo",
    # _misc
    "Greet",
    "OutOfScope",
    "Restart",
    "SessionStart",
    # _search
    "AskForSearchParameters",
    "CheckSearchParameters",
    "RankResults",
    "Search",
    "SetSearchParameters",
    "ShowSearchParameters",
    "ShowSelectedResults",
    # _search_history
    "ClearSearchHistory",
    "AskSearchDeletion",
    "DeleteSearches",
    "ShowSelectedSearches",
    "SetSelectedSearches",
    "ShowSearchHistory",
    "StartSearch",
]
