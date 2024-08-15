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
class ShowSearchHistory(Action):
    """Action used to show the search history."""

    def name(self) -> str:
        return "action_show_search_history"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        store = utils.get_kv_store()
        history = utils.get_slot(tracker, "search_history")
        msg = "Here is your search activity:\n"
        for idx, search_key in enumerate(history):
            name = utils.get_search_title(store[search_key]["parameters"])
            msg += f"{idx + 1}. {name}\n"

        dispatcher.utter_message(text=msg)
        return [SlotSet("selected_searches", None)]


@utils.handle_action_exceptions
class ClearSearchHistory(Action):
    """Action used to clear the search history."""

    def name(self) -> str:
        return "action_clear_search_history"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        return [
            SlotSet("search_history", []),
            SlotSet("selected_searches", None),
        ]


@utils.handle_action_exceptions
class StartSearch(Action):
    """Action used to start a new search and add it to the search activity."""

    def name(self) -> str:
        return "action_start_search"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", []).copy()
        store = utils.get_kv_store()
        search = {"parameters": {}}
        key = store.add(search)
        history.append(key)

        dispatcher.utter_message(response="utter_started_search")
        return [
            SlotSet("search_history", history),
            SlotSet("selected_searches", [len(history) - 1]),
            SlotSet("invalid_location", None),
            SlotSet("invalid_location_reasons", None),
            SlotSet("invalid_place_type", None),
        ]


@utils.handle_action_exceptions
class ShowSelectedSearches(Action):
    """Action used to inform the user about the selected searches."""

    def name(self) -> str:
        return "action_show_selected_searches"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        store = utils.get_kv_store()
        history = utils.get_slot(tracker, "search_history", [])
        selected = utils.get_slot(tracker, "selected_searches", [])
        if len(selected) == 1:
            name = utils.get_search_title(store[history[selected[0]]])
            msg = f"Okay, you have selected '{name}'."
        else:
            msg = "Perfect! You have selected the following searches:\n"
            for idx in selected:
                name = utils.get_search_title(store[history[idx]])
                msg += f"- {name}\n"

        dispatcher.utter_message(text=msg)
        return []


@utils.handle_action_exceptions
class AskSearchDeletion(Action):
    """Action used to ask for confirmation before deleting a search."""

    def name(self) -> str:
        return "action_ask_search_deletion"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        selected = utils.get_slot(tracker, "selected_searches", [])
        if not selected:
            msg = "selected_searches is None but it should have been set"
            raise RuntimeError(msg)

        store = utils.get_kv_store()
        history = utils.get_slot(tracker, "search_history", [])
        if len(selected) == 1:
            search = store[history[selected[0]]]
            name = utils.get_search_title(search["parameters"])
            msg = f"Are you sure you want to delete the search '{name}'?"
        else:
            msg = "Are you sure you want to delete the following searches?\n"
            for idx in selected:
                search = store[history[idx]]
                name = utils.get_search_title(search["parameters"])
                msg += f"- {name}\n"

        dispatcher.utter_message(text=msg)
        return []


@utils.handle_action_exceptions
class DeleteSearches(Action):
    """Action used to delete a search from the search activity."""

    def name(self) -> str:
        return "action_delete_searches"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        selected = set(utils.get_slot(tracker, "selected_searches"))
        history = utils.get_slot(tracker, "search_history", [])
        history = [search for idx, search in enumerate(history) if idx not in selected]
        return [
            SlotSet("search_history", history),
            SlotSet("selected_searches", None),
        ]


@utils.handle_action_exceptions
class SetSelectedSearches(Action):
    """Action used to set the selected searches."""

    def name(self) -> str:
        return "action_set_selected_searches"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        mentions = utils.get_entity_values(tracker, "mention")
        if not mentions:
            return [SlotSet("selected_searches_error", "not_specified")]

        selected, errors = await utils.resolve_mentions(
            tracker,
            selected=utils.get_slot(tracker, "selected_searches", []),
            entity_type="search",
            num_entities=len(utils.get_slot(tracker, "search_history", [])),
        )

        if errors:
            msg = "Sorry, but " + utils.join(errors, sep=", ", last_sep=" and ") + ".\n"
            dispatcher.utter_message(text=msg)
            return [SlotSet("selected_searches_error", "wrong_indices")]

        return [
            SlotSet("selected_searches", selected),
            SlotSet("selected_searches_error", None),
            SlotSet("selected_results", None),
        ]
