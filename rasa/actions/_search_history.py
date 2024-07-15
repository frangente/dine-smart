# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from rasa_sdk import Action
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker
from rasa_sdk.types import DomainDict

from . import utils

_ALL_MENTIONED = ["all", "every", "each", "them", "everything", "these", "those"]

# --------------------------------------------------------------------------- #
# Single actions
# --------------------------------------------------------------------------- #


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
        history = utils.get_slot(tracker, "search_history", [])
        if not history:
            dispatcher.utter_message(response="utter_empty_search_history")
            return []

        msg = "Here is your search activity:\n"
        for idx, search in enumerate(history):
            name = search["title"]
            msg += f"{idx + 1}. - {name}\n"

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
        dispatcher.utter_message(response="utter_cleared_search_history")
        return [
            SlotSet("search_history", []),
            SlotSet("selected_searches", None),
        ]


@utils.handle_action_exceptions
class CheckNumberSelectedSearches(Action):
    """Action to check how many searches the user has selected."""

    def name(self) -> str:
        return "action_check_number_selected_searches"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        if utils.get_slot(tracker, "selected_searches_buffer"):
            return [SlotSet("number_selected_searches", "none")]

        selected = utils.get_slot(tracker, "selected_searches", [])
        if len(selected) == 0:
            return [SlotSet("number_selected_searches", "none")]
        if len(selected) == 1:
            return [SlotSet("number_selected_searches", "single")]

        return [SlotSet("number_selected_searches", "multiple")]


@utils.handle_action_exceptions
class SetSelectedSearches(Action):
    """Action used to set the selected searches."""

    def name(self) -> str:
        return "action_set_selected_searches"

    async def run(  # noqa: C901, PLR0915, PLR0912
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        intent = utils.get_intents(tracker)[0]
        selected = utils.get_slot(tracker, "selected_searches", [])
        if intent == "rectify_selection":
            new_selected = utils.get_slot(tracker, "selected_searches_buffer", [])
        else:
            new_selected = []

        errors = []
        num_searches = len(utils.get_slot(tracker, "search_history", []))
        relative = "search" in tracker.latest_message.get("text", "").lower()
        for mention in utils.get_entity_values(tracker, "mention"):
            if any(word in mention for word in _ALL_MENTIONED):
                if selected:
                    new_selected.extend(selected)
                else:
                    new_selected.extend(range(num_searches))
            elif "current" in mention or "selected" in mention:
                if selected:
                    new_selected.extend(selected)
                else:
                    msg = "you haven't selected any search yet"
                    errors.append(msg)
            elif "last" in mention or "latest" in mention:
                number = await utils.parse_numbers(mention)
                number = number[0] if number else 1
                if relative and len(selected) >= number:
                    new_selected.extend(selected[-number:])
                elif num_searches >= number:
                    new_selected.extend(range(num_searches - number, num_searches))
                else:
                    msg = (
                        f"there are only {num_searches} searches, so I can't select "
                        f"the last {number}"
                    )
                    errors.append(msg)
            elif "next" in mention:
                if len(selected) == 0:
                    msg = (
                        "you haven't selected any search yet, so I can't select the "
                        "next one"
                    )
                    errors.append(msg)
                else:
                    number = await utils.parse_numbers(mention)
                    number = number[0] if number else 1
                    current = max(selected)

                    if current + number < num_searches:
                        new_selected.extend(range(current + 1, current + number + 1))
                    else:
                        msg = (
                            f"there are no more searches, so I can't select the next "
                            f"{number}"
                        )
                        errors.append(msg)
            elif "previous" in mention:
                if len(selected) == 0:
                    msg = (
                        "you haven't selected any search yet, so I can't select the "
                        "previous one"
                    )
                    errors.append(msg)
                else:
                    number = await utils.parse_numbers(mention)
                    number = number[0] if number else 1
                    current = min(selected)

                    if current - number >= 0:
                        new_selected.extend(range(current - number, current))
                    else:
                        msg = (
                            f"there are no previous searches, so I can't select the "
                            f"previous {number}"
                        )
                        errors.append(msg)
            else:
                ordinal = await utils.parse_ordinals(mention)
                number = await utils.parse_numbers(mention)
                if not ordinal and not number:
                    continue

                if not ordinal:
                    number = number[0]
                    if number < 1 or number > num_searches:
                        msg = (
                            f"there are only {num_searches} searches, so I can't "
                            f"select the {utils.int_to_ordinal(number)} one"
                        )
                        errors.append(msg)
                    else:
                        new_selected.append(number - 1)
                else:
                    ordinal = ordinal[0]
                    number = number[0] if number else 1
                    start = (ordinal - 1) * number
                    end = start + number
                    if relative and end < len(selected):
                        new_selected.extend(selected[start:end])
                    elif end < num_searches:
                        new_selected.extend(range(start, end))
                    else:
                        msg = (
                            f"there are only {num_searches} searches, so I can't "
                            f"select the {utils.int_to_ordinal(ordinal)} {number} "
                            f"{utils.agree_with_number('one', end - start)}"
                        )
                        errors.append(msg)

        new_selected = sorted(set(new_selected))
        if errors:
            msg = "Sorry, but " + utils.join(errors, sep=", ", last_sep=" and ")
            dispatcher.utter_message(text=msg)
            return [SlotSet("selected_searches_buffer", new_selected)]

        if not new_selected:
            dispatcher.utter_message(response="utter_no_search_selected")
            return []

        return [
            SlotSet("selected_searches", new_selected),
            SlotSet("selected_searches_buffer", None),
        ]


@utils.handle_action_exceptions
class SelectSearches(Action):
    """Action used to select a search from the search activity."""

    def name(self) -> str:
        return "action_select_searches"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        select_searches = utils.get_slot(tracker, "select_searches", [])
        if not select_searches:
            msg = "select_searches is None but it should have been set"
            raise RuntimeError(msg)

        history = utils.get_slot(tracker, "search_history", [])
        msg = "Perfect! I have selected the following searches:\n"
        for idx in select_searches:
            name = history[idx]["title"]
            msg += f"- {name}\n"

        dispatcher.utter_message(text=msg)
        return []


@utils.handle_action_exceptions
class ConfirmDeleteSearches(Action):
    """Action used to ask for confirmation before deleting a search."""

    def name(self) -> str:
        return "action_confirm_delete_searches"

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

        history = utils.get_slot(tracker, "search_history", [])
        if len(selected) == 1:
            name = history[selected[0]]["title"]
            msg = f"Are you sure you want to delete the search '{name}'?"
        else:
            msg = "Are you sure you want to delete the following searches?\n"
            for idx in selected:
                name = history[idx]["title"]
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
        selected = utils.get_slot(tracker, "selected_searches", [])
        if not selected:
            msg = "selected_searches is None but it should have been set"
            raise RuntimeError(msg)

        selected = set(selected)
        history = [
            search
            for idx, search in enumerate(utils.get_slot(tracker, "search_history", []))
            if idx not in selected
        ]

        dispatcher.utter_message(response="utter_deleted_searches")
        return [
            SlotSet("search_history", history),
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
        history.append({})

        dispatcher.utter_message(response="utter_started_search")
        return [
            SlotSet("search_history", history),
            SlotSet("selected_searches", [len(history) - 1]),
            SlotSet("location", None),
            SlotSet("invalid_location", None),
            SlotSet("invalid_location_reasons", None),
            SlotSet("place_type", None),
            SlotSet("invalid_place_type", None),
        ]
