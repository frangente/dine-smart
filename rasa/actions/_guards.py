# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from rasa_sdk import Action
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker
from rasa_sdk.types import DomainDict

from . import utils


@utils.handle_action_exceptions
class SearchHistoryGuard(Action):
    def name(self) -> str:
        return "action_search_history_guard"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history")
        return [SlotSet("search_history", history)]


@utils.handle_action_exceptions
class SelectedSearchesGuard(Action):
    def name(self) -> str:
        return "action_selected_searches_guard"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        selected = utils.get_slot(tracker, "selected_searches")
        return [SlotSet("selected_searches", selected)]
