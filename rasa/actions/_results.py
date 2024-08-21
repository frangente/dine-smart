# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from gcp.maps import places
from rasa_sdk import Action, Tracker
from rasa_sdk.events import FollowupAction, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from . import utils

_PAGE_SIZE = 5
_SELECT_INTENTS = {
    "show_results",
    "select_results",
    "select",
    "ask_address",
    "ask_contact",
    "ask_price_level",
    "ask_rating",
    "ask_website",
    "ask_allows_animals",
    "ask_good_for_children",
    "ask_parking_options",
    "ask_payment_options",
    "ask_outdoor_seating",
    "ask_reservable",
    "ask_restroom",
    "ask_vegetarian",
    "ask_takeout",
    "ask_previous_info",
}


@utils.handle_action_exceptions
class SetSelectedResults(Action):
    """Action to set the selected results."""

    def name(self) -> str:
        return "action_set_selected_results"

    async def run(  # noqa: PLR0911
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", [])
        selected_search = utils.get_slot(tracker, "selected_searches", [])[0]
        search = utils.get_kv_store().get_search(history[selected_search])
        results = search.results or []

        if len(results) == 0:
            return [
                SlotSet("selected_results", None),
                SlotSet("selected_results_error", "no_results"),
            ]

        mentions = utils.get_entity_values(tracker, "mention")
        if not mentions:
            if len(results) == 1:
                return [
                    SlotSet("selected_results", [0]),
                    SlotSet("selected_results_error", None),
                ]

            intents = set(utils.get_last_intents(tracker))
            if "show_results" in intents:
                return [
                    SlotSet("selected_results", list(range(len(results)))),
                    SlotSet("selected_results_error", None),
                ]

            if any(intent.startswith("ask_") for intent in intents):
                selected = utils.get_slot(tracker, "selected_results")
                error = utils.get_slot(tracker, "selected_results_error")
                return [
                    SlotSet("selected_results", selected),
                    SlotSet("selected_results_error", error),
                ]

            return [
                SlotSet("selected_results", None),
                SlotSet("selected_results_error", "no_selection"),
            ]

        selected, errors = await utils.resolve_mentions(
            tracker,
            selected=utils.get_slot(tracker, "selected_results", []),
            num_entities=len(results),
            entity_type=["result", "place"],
        )

        if errors:
            msg = "Sorry, but " + utils.join(errors, sep=", ", last_sep=" and ") + ".\n"
            dispatcher.utter_message(text=msg)
            return [SlotSet("selected_results_error", "invalid_selection")]

        if len(selected) == 0:
            return [
                SlotSet("selected_results", None),
                SlotSet("selected_results_error", "no_results_found"),
            ]

        return [
            SlotSet("selected_results", selected),
            SlotSet("selected_results_error", None),
        ]


@utils.handle_action_exceptions
class ShowSelectedResults(Action):
    """Action to show the selected search results to the user."""

    def name(self) -> str:
        return "action_show_selected_results"

    async def run(  # noqa: C901, PLR0912
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", [])
        idx = utils.get_slot(tracker, "selected_searches")[0]
        search = utils.get_kv_store().get_search(history[idx])
        results = search.results or []

        selected: list[int] = utils.get_slot(tracker, "selected_results", [])
        if len(selected) == 1:
            place = results[selected[0]]
            if place.display_name is None:
                msg = "place.display_name is None"
                raise RuntimeError(msg)

            primary_type = "place"
            if place.primary_type_display_name:
                primary_type = place.primary_type_display_name.text

            msg = f"Here are the details for the {primary_type} {place.display_name.text}:\n"  # noqa: E501
            msg += f"- it is located at {place.short_formatted_address}\n"
            if place.national_phone_number:
                msg += f"- you can call them at {place.national_phone_number}\n"
            if place.rating:
                msg += f"- it has a rating of {place.rating} out of 5\n"
            match place.price_level:
                case None | places.PriceLevel.UNSPECIFIED:
                    pass
                case places.PriceLevel.FREE:
                    msg += "- it does not charge for its services\n"
                case places.PriceLevel.INEXPENSIVE:
                    msg += "- it is not expensive\n"
                case places.PriceLevel.MODERATE:
                    msg += "- it is moderately priced\n"
                case places.PriceLevel.EXPENSIVE:
                    msg += "- it is expensive\n"
                case places.PriceLevel.VERY_EXPENSIVE:
                    msg += "- it is very expensive\n"
        elif len(selected) == len(results):
            msg = "Here all the results:\n"
            for i, result in enumerate(results):
                msg += f"{i + 1}. {utils.get_place_title(result)}\n"
        else:
            msg = "Here are the selected results:\n"
            for i in selected:
                msg += f"{i + 1}. {utils.get_place_title(results[i])}\n"

        dispatcher.utter_message(msg)
        if len(selected) == 1 and utils.get_slot(tracker, "suggest_booking"):
            place = results[selected[0]]
            if place.reservable:
                return [FollowupAction("action_suggest_booking")]

        return []


@utils.handle_action_exceptions
class CountSelectedResults(Action):
    """Action used to count the selected results."""

    def name(self) -> str:
        return "action_count_selected_results"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        selected = utils.get_slot(tracker, "selected_results", [])
        if len(selected) == 0:
            return [SlotSet("selected_results_count", "zero")]

        if len(selected) == 1:
            return [SlotSet("selected_results_count", "one")]

        return [SlotSet("selected_results_count", "multiple")]
