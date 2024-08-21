# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from rasa_sdk import Action
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker
from rasa_sdk.types import DomainDict

from . import utils

_SELECT_INTENTS = {
    "show_searches",
    "select_searches",
    "delete_searches",
    "select",
    "delete",
}
_PAGE_SIZE = 5


@utils.handle_action_exceptions
class SetSelectedSearches(Action):
    """Action used to set the selected searches."""

    def name(self) -> str:
        return "action_set_selected_searches"

    async def run(  # noqa: PLR0911
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", [])
        if len(history) == 0:
            return [
                SlotSet("selected_searches", None),
                SlotSet("selected_searches_error", "no_searches"),
            ]

        mentions = utils.get_entity_values(tracker, "mention")
        if not mentions:
            if len(history) == 1:
                return [
                    SlotSet("selected_searches", [0]),
                    SlotSet("selected_searches_error", None),
                ]

            intents = utils.get_last_intents(tracker)
            text = tracker.latest_message["text"]
            if "show_searches" in intents or "history" in text or "activity" in text:
                history = utils.get_slot(tracker, "search_history", [])
                selected = list(range(len(history)))
                return [
                    SlotSet("selected_searches", selected),
                    SlotSet("selected_searches_error", None),
                ]

            return [
                SlotSet("selected_searches", None),
                SlotSet("selected_searches_error", "no_selection"),
            ]

        selected, errors = await utils.resolve_mentions(
            tracker,
            selected=utils.get_slot(tracker, "selected_searches", []),
            entity_type="search",
            num_entities=len(history),
        )

        if errors:
            msg = "Sorry, but " + utils.join(errors, sep=", ", last_sep=" and ") + ".\n"
            dispatcher.utter_message(text=msg)
            return [SlotSet("selected_searches_error", "invalid_selection")]

        if len(selected) == 0:
            return [
                SlotSet("selected_searches", None),
                SlotSet("selected_searches_error", "no_searches_found"),
                SlotSet("selected_results", None),
            ]

        if len(selected) == 1:
            store = utils.get_kv_store()
            search = store.get_search(history[selected[0]])
            selected_results = list(range(min(len(search.results or []), _PAGE_SIZE)))

            return [
                SlotSet("selected_searches", selected),
                SlotSet("selected_searches_error", None),
                SlotSet("selected_results", selected_results),
                SlotSet("suggest_booking", False),  # noqa: FBT003
            ]

        return [
            SlotSet("selected_searches", selected),
            SlotSet("selected_searches_error", None),
            SlotSet("selected_results", None),
            SlotSet("suggest_booking", False),  # noqa: FBT003
        ]


@utils.handle_action_exceptions
class ShowSelectedSearches(Action):
    """Action used to show the selected searches."""

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
            search = store.get_search(history[selected[0]])
            msg = f"Here is the {utils.get_search_title(search.parameters)}\n"
            results = search.results or []
            if len(results) == 0:
                msg += "There are no results for this search."
            elif len(results) <= _PAGE_SIZE:
                msg += "The results of the search are:\n"
                for i, result in enumerate(results):
                    msg += f"{i + 1}. {utils.get_place_title(result)}\n"
            else:
                msg += f"The top {_PAGE_SIZE} results of the search are:\n"
                for i, result in enumerate(results[:_PAGE_SIZE]):
                    msg += f"{i + 1}. {utils.get_place_title(result)}\n"
        elif len(selected) == len(history):
            msg = "Here is your search history:\n"
            for idx, search_id in enumerate(history):
                search = store.get_search(search_id)
                msg += f"{idx + 1}. {utils.get_search_title(search.parameters)}\n"
        else:
            msg = "Here are the selected searches:\n"
            for idx in selected:
                search = store.get_search(history[idx])
                msg += f"{idx + 1}. {utils.get_search_title(search.parameters)}\n"

        dispatcher.utter_message(text=msg)
        return []


@utils.handle_action_exceptions
class DeleteSelectedSearches(Action):
    """Action used to delete the selected searches."""

    def name(self) -> str:
        return "action_delete_selected_searches"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", [])
        selected = set(utils.get_slot(tracker, "selected_searches", []))
        history = [search for i, search in enumerate(history) if i not in selected]

        dispatcher.utter_message(response="utter_deleted_searches")
        return [SlotSet("search_history", history), SlotSet("selected_searches", None)]


@utils.handle_action_exceptions
class ConfirmDeleteSelectedSearches(Action):
    """Action used to ask the user to confirm the deletion of the selected searches."""

    def name(self) -> str:
        return "action_confirm_delete_selected_searches"

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
            search = store.get_search(history[selected[0]])
            title = utils.get_search_title(search.parameters)
            msg = f"Are you sure you want to delete: {title}?"
        elif len(selected) == len(history):
            msg = "Are you sure you want to delete all your search history?"
        else:
            msg = "Are you sure you want to delete the following searches?\n"
            for idx in selected:
                search = store.get_search(history[idx])
                msg += f"- {utils.get_search_title(search.parameters)}\n"

        dispatcher.utter_message(text=msg)
        return []


@utils.handle_action_exceptions
class CountSelectedSearches(Action):
    """Action used to count the selected searches."""

    def name(self) -> str:
        return "action_count_selected_searches"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        selected = utils.get_slot(tracker, "selected_searches", [])
        if len(selected) == 0:
            return [SlotSet("selected_searches_count", "zero")]

        if len(selected) == 1:
            return [SlotSet("selected_searches_count", "one")]

        return [SlotSet("selected_searches_count", "multiple")]
