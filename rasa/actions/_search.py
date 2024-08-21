# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from gcp.maps import places
from rasa_sdk import Action, FormValidationAction, Tracker
from rasa_sdk.events import FollowupAction, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from rasa.shared.nlu.constants import ENTITY_ATTRIBUTE_VALUE

from . import utils
from .records import SearchData, SearchParameters

_PAGE_SIZE = 5
_ALTERNATIVE_PARAMETERS = [
    "activity",
    "meal_type",
    "cuisine_type",
    "place_type",
    "place_name",
]

# --------------------------------------------------------------------------- #
# Form-related Actions
# --------------------------------------------------------------------------- #


@utils.handle_action_exceptions
class ValidateSearchForm(FormValidationAction):
    """Action used to validate the search form."""

    def name(self) -> str:
        return "validate_search_form"

    async def required_slots(
        self,
        domain_slots: list[str],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[str]:
        alt_slots_set = any(
            utils.get_slot(tracker, f"search_{slot}") is not None
            for slot in _ALTERNATIVE_PARAMETERS
        )
        if alt_slots_set:
            return ["search_location"]

        return ["search_place_type", "search_location"]


@utils.handle_action_exceptions
class SetSearchPlaceType(Action):
    """Action used to set the search place type."""

    def name(self) -> str:
        return "action_set_search_place_type"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        entities = utils.get_entities(tracker, "place_type")
        if not entities:
            return []

        if entities[0].get("is_correct", True):
            place_type = entities[0][ENTITY_ATTRIBUTE_VALUE]
            error = False
        else:
            place_type = None
            error = True

        return [
            SlotSet("search_place_type", place_type),
            SlotSet("search_place_type_error", error),
        ]


@utils.handle_action_exceptions
class SetSearchLocation(Action):
    """Action used to set the search location."""

    def name(self) -> str:
        return "action_set_search_location"

    async def run(  # noqa: PLR0911
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        user_location = utils.get_slot(tracker, "user_location")
        if utils.is_user_location(tracker.latest_message["text"]):
            if user_location is None:
                return [
                    SlotSet("search_location", None),
                    SlotSet("search_location_error", [("unknown_user_location", None)]),
                ]

            return [
                SlotSet("search_location", user_location),
                SlotSet("search_location_error", None),
            ]

        entities = utils.get_entity_values(tracker, "location")
        if not entities:
            location = utils.get_slot(tracker, "search_location")
            error = utils.get_slot(tracker, "search_location_error")
            if location or error:
                return []

            open_now = utils.get_slot(tracker, "search_open_now")
            if open_now and user_location:
                return [
                    SlotSet("search_location", user_location),
                    SlotSet("search_location_error", None),
                ]

            return []

        entity = entities[0]
        error = utils.get_slot(tracker, "search_location_error", [])
        fill_user_location = [
            "inform_my_location" in utils.get_last_intents(tracker),
            any(reason == "unknown_user_location" for reason, _ in error),
        ]
        if error and error[-1][0] == "ambiguous":
            entity = utils.merge_locations(error[-1][1], entity)

        candidates = await utils.find_location(
            entity,
            utils.deserialize(places.Place, user_location) if user_location else None,
        )
        if len(candidates) != 1:
            error.append(("ambiguous" if candidates else "not_found", entity))
            location = None
            return [
                SlotSet("search_location", location),
                SlotSet("search_location_error", error),
            ]

        location = utils.serialize(candidates[0])
        slots = [
            SlotSet("search_location", location),
            SlotSet("search_location_error", None),
        ]
        if fill_user_location:
            slots.append(SlotSet("user_location", location))

        return slots


@utils.handle_action_exceptions
class SetSearchOpenNow(Action):
    """Action used to set the search open now flag."""

    def name(self) -> str:
        return "action_set_search_open_now"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        open_now = None
        for intent in utils.get_last_intents(tracker):
            if intent.endswith("now"):
                open_now = True
                break

        if open_now is None:
            return []

        return [SlotSet("search_open_now", open_now)]


@utils.handle_action_exceptions
class SetSearchActivity(Action):
    """Action used to set the search activity."""

    def name(self) -> str:
        return "action_set_search_activity"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        activity = None
        for intent in utils.get_last_intents(tracker):
            if "eat" in intent:
                activity = "eat"
                break
            if "drink" in intent:
                activity = "drink"
                break

        if activity is None:
            return []

        return [SlotSet("search_activity", activity)]


@utils.handle_action_exceptions
class SetSearchPriceRange(Action):
    """Action used to set the search price range."""

    def name(self) -> str:
        return "action_set_search_price_range"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        price_range = None
        for intent in utils.get_last_intents(tracker):
            match intent:
                case "inform_price_range_any":
                    price_range = "any"
                case "inform_price_range_expensive":
                    price_range = "expensive"
                case "inform_price_range_moderate":
                    price_range = "moderate"
                case "inform_price_range_inexpensive":
                    price_range = "inexpensive"
                case _:
                    continue

        if price_range is None:
            return []

        return [SlotSet("search_price_range", price_range)]


@utils.handle_action_exceptions
class SetSearchQuality(Action):
    """Action used to set the search quality."""

    def name(self) -> str:
        return "action_set_search_quality"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        quality = None
        for intent in utils.get_last_intents(tracker):
            match intent:
                case "inform_quality_any":
                    quality = "any"
                case "inform_quality_excellent":
                    quality = "excellent"
                case "inform_quality_moderate":
                    quality = "moderate"
                case _:
                    continue

        if quality is None:
            return []

        return [SlotSet("search_quality", quality)]


@utils.handle_action_exceptions
class AskSearchPlaceType(Action):
    """Action to ask the user for the search place type."""

    def name(self) -> str:
        return "action_ask_search_place_type"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        error = utils.get_slot(tracker, "search_place_type_error")
        if error:
            dispatcher.utter_message(response="utter_invalid_place_type")
        else:
            dispatcher.utter_message(response="utter_ask_place_type")

        return []


@utils.handle_action_exceptions
class AskSearchLocation(Action):
    """Action to ask the user for the search location."""

    def name(self) -> str:
        return "action_ask_search_location"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        error = utils.get_slot(tracker, "search_location_error")

        place_type = utils.get_slot(tracker, "search_place_type")
        activity = utils.get_slot(tracker, "search_activity")
        if place_type:
            place_type = utils.pluralize(place_type)
        elif activity == "eat":
            place_type = "places to eat"
        elif activity == "drink":
            place_type = "places to have a drink"
        else:
            place_type = "places"

        if not error:
            # the user never provided a location for the search
            open_now = utils.get_slot(tracker, "search_open_now")
            place_name = utils.get_slot(tracker, "search_place_name")

            if open_now:
                dispatcher.utter_message(
                    response="utter_ask_user_location", place_type=place_type
                )
            elif place_name:
                dispatcher.utter_message(
                    response="utter_ask_location_place_name", place_name=place_name
                )
            else:
                dispatcher.utter_message(
                    response="utter_ask_location", place_type=place_type
                )
        elif error[-1][0] == "unknown_user_location":
            dispatcher.utter_message(response="utter_need_user_location")
        elif error[-1][0] == "ambiguous":
            dispatcher.utter_message(
                response="utter_ambiguous_location", location=error[-1][1]
            )
        else:
            dispatcher.utter_message(
                response="utter_location_not_found", location=error[-1][1]
            )

        return []


# --------------------------------------------------------------------------- #
# Search-management Actions
# --------------------------------------------------------------------------- #


@utils.handle_action_exceptions
class StartSearch(Action):
    """Action to start the search process."""

    def name(self) -> str:
        return "action_start_search"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", [])
        intents = utils.get_last_intents(tracker)
        if any(intent.startswith("inform") for intent in intents):
            # ther user is modifying an existing search
            idx = utils.get_slot(tracker, "selected_searches", [])[0]
            search = utils.get_kv_store().get_search(history[idx])

            return [
                SlotSet("search_location", utils.serialize(search.parameters.location)),
                SlotSet("search_location_error", None),
                SlotSet("search_place_type", search.parameters.place_type),
                SlotSet("search_place_type_error", None),
                SlotSet("search_place_name", search.parameters.place_name),
                SlotSet("search_open_now", search.parameters.open_now),
                SlotSet("search_meal_type", search.parameters.meal_type),
                SlotSet("search_cuisine_type", search.parameters.cuisine_type),
                SlotSet("search_activity", search.parameters.activity),
                SlotSet("search_price_range", search.parameters.price_range),
                SlotSet("search_quality", search.parameters.quality),
            ]

        # the user is creating a new search
        history = history.copy()
        history.append(None)

        datetimes = utils.get_entity_values(tracker, "datetime")
        suggest_booking = len(datetimes) > 0

        dispatcher.utter_message(response="utter_start_search")
        return [
            SlotSet("search_history", history),
            SlotSet("selected_searches", [len(history) - 1]),
            SlotSet("selected_results", None),
            SlotSet("search_location", None),
            SlotSet("search_location_error", None),
            SlotSet("search_place_type", None),
            SlotSet("search_place_type_error", None),
            SlotSet("search_place_name", None),
            SlotSet("search_open_now", None),
            SlotSet("search_meal_type", None),
            SlotSet("search_cuisine_type", None),
            SlotSet("search_activity", None),
            SlotSet("search_price_range", None),
            SlotSet("search_quality", None),
            SlotSet("suggest_booking", suggest_booking),
        ]


@utils.handle_action_exceptions
class CreateSearch(Action):
    """Action to create a search object."""

    def name(self) -> str:
        return "action_create_search"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", [])
        idx = utils.get_slot(tracker, "selected_searches", [])[0]

        location = utils.get_slot(tracker, "search_location")
        location = utils.deserialize(places.Place, location)

        parameters = SearchParameters(
            location=location,
            place_type=utils.get_slot(tracker, "search_place_type"),
            place_name=utils.get_slot(tracker, "search_place_name"),
            open_now=utils.get_slot(tracker, "search_open_now"),
            meal_type=utils.get_slot(tracker, "search_meal_type"),
            cuisine_type=utils.get_slot(tracker, "search_cuisine_type"),
            activity=utils.get_slot(tracker, "search_activity"),
            price_range=utils.get_slot(tracker, "search_price_range"),
            quality=utils.get_slot(tracker, "search_quality"),
        )

        search = SearchData(parameters)

        store = utils.get_kv_store()
        if history[idx] is not None:
            # the user was modifying an existing search
            store.update_search(history[idx], search)
            return []

        # the user was starting a new search
        history = history.copy()
        history[idx] = store.add_search(search)

        return [
            SlotSet("search_history", history),
            SlotSet("selected_searches", [idx]),
            SlotSet("selected_searches_error", None),
        ]


@utils.handle_action_exceptions
class CancelSearch(Action):
    """Action to cancel the search process."""

    def name(self) -> str:
        return "action_cancel_search"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", [])
        idx = utils.get_slot(tracker, "selected_searches", [])[0]

        if history[idx] is None:
            # the user was starting a new search
            dispatcher.utter_message(response="utter_cancel_search")
            history = history.copy()
            history.pop(idx)
            return [
                SlotSet("search_history", history),
                SlotSet("selected_searches", []),
            ]

        # the user was modifying an existing search, so we don't need to do anything
        dispatcher.utter_message(response="utter_cancel_modify_search")
        return []


# --------------------------------------------------------------------------- #
# Search-related Actions
# --------------------------------------------------------------------------- #


@utils.handle_action_exceptions
class Search(Action):
    """Action to search for places using the Google Places API."""

    def name(self) -> str:
        return "action_search"

    async def run(  # noqa: C901, PLR0912, PLR0915
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", []).copy()
        idx = utils.get_slot(tracker, "selected_searches")[0]
        store = utils.get_kv_store()
        search = store.get_search(history[idx])

        results = await utils.find_places(search.parameters)
        if len(results) == 0:
            if search.results is None:
                msg = "I couldn't find any places matching your search criteria. "
                msg += "Try loosening them a bit."
            elif len(search.results) == 0:
                msg = "Sorry, but I still cannot find any places."
            else:
                msg = "These new search criteria may be too restrictive because I "
                msg += "cannot find any places satisfying them."
        elif len(results) == 1:
            if search.results is None:
                msg = "I found only one place matching your search criteria: "
                msg += utils.get_place_title(results[0])
            elif len(search.results) == 0:
                msg = "Well at least now I found one place: "
                msg += utils.get_place_title(results[0])
            elif len(search.results) == 1:
                msg = "Even now, I found only one place: "
                msg += utils.get_place_title(results[0])
            else:
                msg = "Using these new search criteria, I found only one place: "
                msg += utils.get_place_title(results[0])
        elif len(results) <= _PAGE_SIZE:
            if search.results is None:
                msg = "Here are all the results I found:\n"
                for i, result in enumerate(results, start=1):
                    msg += f"{i}. {utils.get_place_title(result)}\n"
            elif len(search.results) < len(results):
                msg = "With these new search criteria, I found more results:\n"
                for i, result in enumerate(results, start=1):
                    msg += f"{i}. {utils.get_place_title(result)}\n"
            else:
                msg = "Here are all the results I found with the new search criteria:\n"
                for i, result in enumerate(results, start=1):
                    msg += f"{i}. {utils.get_place_title(result)}\n"
        else:  # noqa: PLR5501
            if search.results is None:
                msg = "I found multiple places matching your search criteria. "
                msg += f"Here are the top {_PAGE_SIZE}:\n"
                for i, result in enumerate(results[:_PAGE_SIZE], start=1):
                    msg += f"{i}. {utils.get_place_title(result)}\n"
            elif len(search.results) < len(results):
                msg = f"Now I found many more places. Here are the top {_PAGE_SIZE}:\n"
                for i, result in enumerate(results[:_PAGE_SIZE], start=1):
                    msg += f"{i}. {utils.get_place_title(result)}\n"
            else:
                msg = f"Here are the new top {_PAGE_SIZE} results:\n"
                for i, result in enumerate(results[:_PAGE_SIZE], start=1):
                    msg += f"{i}. {utils.get_place_title(result)}\n"

        search.results = results
        store.update_search(history[idx], search)

        dispatcher.utter_message(msg)
        events = [
            SlotSet("selected_results", list(range(min(len(results), _PAGE_SIZE))))
        ]
        if (
            len(results) == 1
            and utils.get_slot(tracker, "suggest_booking")
            and results[0].reservable
        ):
            events.append(FollowupAction("action_suggest_booking"))

        return events


@utils.handle_action_exceptions
class ChangeSearchRankBy(Action):
    """Action to change the ranking of the search results."""

    def name(self) -> str:
        return "action_change_search_rank_by"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        rank_by = None
        for intent in utils.get_last_intents(tracker):
            match intent:
                case "rank_results_by_relevance":
                    rank_by = "relevance"
                    break
                case "rank_results_by_distance":
                    rank_by = "distance"
                    break
                case "rank_results_by_unsupported":
                    dispatcher.utter_message(response="utter_unsupported_rank_by")
                    return []
                case _:
                    continue

        if rank_by is None:
            msg = "rank_by is None, but it should not be."
            raise RuntimeError(msg)

        history = utils.get_slot(tracker, "search_history", [])
        idx = utils.get_slot(tracker, "selected_searches")[0]
        store = utils.get_kv_store()
        search = store.get_search(history[idx])

        if search.parameters.rank_by == rank_by:
            dispatcher.utter_message(
                response="utter_already_ranked_by", rank_by=rank_by
            )
            return []

        search.parameters.rank_by = rank_by

        if len(search.results or []) < 2:
            store.update_search(history[idx], search)
            dispatcher.utter_message(response="utter_changed_rank_by", rank_by=rank_by)
            return []

        results = await utils.find_places(search.parameters)
        if len(results) <= _PAGE_SIZE:
            msg = f"Here are all the results sorted by {rank_by}:"
        else:
            msg = f"Here are the top {_PAGE_SIZE} results sorted by {rank_by}:"

        for i, result in enumerate(results[:_PAGE_SIZE], start=1):
            msg += f"\n{i}. {utils.get_place_title(result)}"

        search.results = results
        store.update_search(history[idx], search)

        dispatcher.utter_message(msg)

        return [SlotSet("selected_results", list(range(min(len(results), _PAGE_SIZE))))]


# --------------------------------------------------------------------------- #
# Search parameters Actions
# --------------------------------------------------------------------------- #


@utils.handle_action_exceptions
class ShowSearchParameters(Action):
    def name(self) -> str:
        return "action_show_search_parameters"

    async def run(  # noqa: C901, PLR0912
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", [])
        idx = utils.get_slot(tracker, "selected_searches")[0]
        search = utils.get_kv_store().get_search(history[idx])

        if search.parameters.place_type:
            place_type = utils.singularize(search.parameters.place_type)
        elif search.parameters.activity == "eat":
            place_type = "place where to eat"
        elif search.parameters.activity == "drink":
            place_type = "place where to drink"
        else:
            place_type = "place"

        location = search.parameters.location.short_formatted_address

        msg = "Here are the search details:\n"
        if search.parameters.place_name:
            place_name = search.parameters.place_name
            msg += (
                f"- you are looking for a {place_type} called {place_name} "
                f"near {location}"
            )
        else:
            msg += f"- you are looking for a {place_type}"
            if search.parameters.meal_type is not None:
                msg += f" for {search.parameters.meal_type}"
            if search.parameters.cuisine_type is not None:
                msg += f" with {search.parameters.cuisine_type} cuisine"

            msg += f" near {location}"

        if search.parameters.open_now:
            msg += f"\n- the {place_type} should be open now"

        match search.parameters.quality:
            case None | "any":
                pass
            case "excellent":
                msg += f"\n- the {place_type} should have excellent reviews"
            case "moderate":
                msg += f"\n- the {place_type} should have good reviews"

        match search.parameters.price_range:
            case None | "any":
                pass
            case "expensive":
                msg += f"\n- the {place_type} should be expensive"
            case "moderate":
                msg += f"\n- the {place_type} should be moderately priced"
            case "inexpensive":
                msg += f"\n- the {place_type} should be inexpensive"

        msg += f"\n- the results are ranked by {search.parameters.rank_by}"
        dispatcher.utter_message(msg)

        return []
