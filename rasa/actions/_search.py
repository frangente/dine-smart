# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from gcp.maps import places
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from rasa.shared.nlu.constants import ENTITY_ATTRIBUTE_VALUE

from . import utils

_PAGE_SIZE = 5

# --------------------------------------------------------------------------- #
# Form-related Actions
# --------------------------------------------------------------------------- #


@utils.handle_action_exceptions
class SetSearchParameters(Action):
    """Sets the search parameters based on the user's input."""

    def name(self) -> str:
        return "action_set_search_key"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", [])
        idx = utils.get_slot(tracker, "selected_searches")[0]

        store = utils.get_kv_store()
        parameters = store[history[idx]]["parameters"]

        error_slots = {}

        # parameters for which no validation check is needed
        valid_params = {
            "place_name": await self._get_place_name(tracker),
            "open_now": await self._get_open_now(tracker),
            "activity": await self._get_activity(tracker),
            "cuisine_type": await self._get_cuisine_type(tracker),
            "price_range": await self._get_price_range(tracker),
            "quality": await self._get_quality(tracker),
        }
        valid_params = {k: v for k, v in valid_params.items() if v is not None}
        parameters.update(valid_params)

        location, errors = await self._extract_location(tracker, parameters)
        if location or errors:
            parameters["location"] = location
            error_slots.update(errors)

        place_type, errors = await self._extract_place_type(tracker, parameters)
        if place_type or errors:
            parameters["place_type"] = place_type
            error_slots.update(errors)

        new_search = {"parameters": parameters}
        store[history[idx]] = new_search

        events = [SlotSet(k, v) for k, v in error_slots.items()]

        if utils.validate_search_parameters(parameters):
            events.append(SlotSet("search_key", history[idx]))
        else:
            events.append(SlotSet("search_key", None))

        return events

    async def _extract_location(  # noqa: PLR0912
        self,
        tracker: Tracker,
        parameters: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        user_location = utils.get_slot(tracker, "user_location")
        entities = utils.get_entity_values(tracker, "location")
        if not entities:
            slots = {}
            if parameters.get("location"):
                location = parameters["location"]
            elif user_location and parameters.get("open_now", False):
                location = user_location
            else:
                location = None
        else:
            entity = entities[0]
            if utils.is_user_location(entity):
                if not user_location:
                    location = None
                    slots = {
                        "invalid_location": None,
                        "invalid_location_reasons": ["unknown_user_location"],
                    }
                else:
                    location = user_location
                    slots = {
                        "invalid_location": None,
                        "invalid_location_reasons": None,
                    }
            else:
                reasons = utils.get_slot(tracker, "invalid_location_reasons", [])
                fill_user_location = (
                    "inform_my_location" in utils.get_intents(tracker)
                    or "unknown_user_location" in reasons
                )
                if reasons and reasons[-1] == "ambiguous":
                    invalid = utils.get_slot(tracker, "invalid_location")
                    if invalid is None:
                        msg = "invalid_location is None, but it should not be."
                        raise RuntimeError(msg)

                    location = utils.merge_locations(invalid, entity)

                candidates = await utils.find_location(
                    entity,
                    utils.deserialize(places.Place, user_location)
                    if user_location
                    else None,
                )
                if len(candidates) != 1:
                    reasons += ["ambiguous" if candidates else "not_found"]
                    location = None
                    slots = {
                        "invalid_location": location,
                        "invalid_location_reasons": reasons,
                    }
                else:
                    location = utils.serialize(candidates[0])
                    slots = {
                        "invalid_location": None,
                        "invalid_location_reasons": None,
                    }

                    if fill_user_location:
                        slots["user_location"] = location  # type: ignore

        return location, slots

    async def _extract_place_type(
        self,
        tracker: Tracker,
        parameters: dict[str, Any],
    ) -> tuple[str | None, dict[str, Any]]:
        types = utils.get_entities(tracker, "place_type")
        if not types:
            return parameters.get("place_type"), {}

        if types[0].get("is_correct", True):
            place_type = types[0][ENTITY_ATTRIBUTE_VALUE]
            invalid = False
        else:
            place_type = None
            invalid = True

        return place_type, {"invalid_place_type": invalid}

    async def _get_place_name(self, tracker: Tracker) -> str | None:
        name = utils.get_entity_values(tracker, "place_name")
        return name[0] if name else None

    async def _get_open_now(self, tracker: Tracker) -> bool | None:
        open_now = None
        for intent in utils.get_intents(tracker):
            if intent.endswith("now"):
                open_now = True
                break

        return open_now

    async def _get_activity(self, tracker: Tracker) -> str | None:
        activity = None
        for intent in utils.get_intents(tracker):
            if "eat" in intent:
                activity = "eat"
                break
            if "drink" in intent:
                activity = "drink"
                break

        return activity

    async def _get_cuisine_type(self, tracker: Tracker) -> str | None:
        types = utils.get_entity_values(tracker, "cuisine_type")
        return types[0] if types else None

    async def _get_price_range(self, tracker: Tracker) -> str | None:
        price_range = None
        for intent in utils.get_intents(tracker):
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

        return price_range

    async def _get_quality(self, tracker: Tracker) -> str | None:
        quality = None
        for intent in utils.get_intents(tracker):
            match intent:
                case "inform_quality_any":
                    quality = "any"
                case "inform_quality_excellent":
                    quality = "excellent"
                case "inform_quality_moderate":
                    quality = "moderate"
                case _:
                    continue

        return quality


@utils.handle_action_exceptions
class AskForSearchParameters(Action):
    """Asks the user for the search parameters."""

    def name(self) -> str:
        return "action_ask_search_key"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        search_history = utils.get_slot(tracker, "search_history", [])
        idx = utils.get_slot(tracker, "selected_searches")[0]

        search_key = search_history[idx]
        store = utils.get_kv_store()
        parameters = store[search_key].get("parameters", {})

        if not utils.validate_search_parameters(parameters, include_location=False):
            self._ask_place_type(dispatcher, tracker, parameters)
        elif parameters.get("location") is None:
            self._ask_location(dispatcher, tracker, parameters)

        return []

    def _ask_place_type(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        parameters: dict[str, Any],
    ) -> None:
        invalid = utils.get_slot(tracker, "invalid_place_type", False)  # noqa: FBT003
        if invalid:
            dispatcher.utter_message(response="utter_invalid_place_type")
        else:
            dispatcher.utter_message(response="utter_ask_place_type")

    def _ask_location(  # noqa: PLR0912, C901
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        parameters: dict[str, Any],
    ) -> None:
        invalid = utils.get_slot(tracker, "invalid_location", None)
        reasons = utils.get_slot(tracker, "invalid_location_reasons", [])

        place_type = parameters.get("place_type")
        if place_type is not None:
            place_type = utils.pluralize(place_type)
        elif parameters.get("activity") == "eat":
            place_type = "places to eat"
        elif parameters.get("activity") == "drink":
            place_type = "places to have a drink"
        else:
            place_type = "places"

        if not reasons:
            # the user never provided a location for the search, but we may have
            # already asked them for their location
            asked_count = utils.count_action_inside_form(tracker, self.name())
            open_now = parameters.get("open_now", False)
            name = parameters.get("place_name")

            if asked_count > 2:
                # the user has been asked for the location multiple times, but they
                # never provided it, so we ask them if they want to stop the search
                dispatcher.utter_message(response="utter_inform_how_stop_search")
            elif open_now:
                # if the user needs to find a place now, we should look for
                # places near their location
                response = "utter_ask_user_location"
                if asked_count > 1:
                    response += "_2"
                dispatcher.utter_message(response=response, place_type=place_type)
            elif name is not None:
                # if the user is looking for a specific place, we should ask them
                # for the location
                response = "utter_ask_location_place_name"
                if asked_count > 1:
                    response += "_2"
                dispatcher.utter_message(response=response, place_name=name)
            else:
                # if the user is looking for places for the future or just
                # for information, we ask them for the location
                response = "utter_ask_location"
                if asked_count > 0:
                    response += "_2"
                dispatcher.utter_message(response=response, place_type=place_type)
        elif reasons[-1] == "unknown_user_location":
            # the user has stated that the search location should be their location
            # but we don't know their location yet
            dispatcher.utter_message(response="utter_need_user_location")
        elif reasons[-1] == "ambiguous":
            response = "utter_ambiguous_location"
            dispatcher.utter_message(response=response, location=invalid)
        else:
            response = "utter_location_not_found"
            dispatcher.utter_message(response=response, location=invalid)


@utils.handle_action_exceptions
class CheckSearchParameters(Action):
    """Checks if all the required search parameters have been provided."""

    def name(self) -> str:
        return "action_check_search_parameters"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", [])
        idx = utils.get_slot(tracker, "selected_searches")[0]
        search = utils.get_kv_store()[history[idx]]

        return [
            SlotSet(
                "all_required_parameters_set",
                utils.validate_search_parameters(search.get("parameters", {})),
            )
        ]


@utils.handle_action_exceptions
class ShowSearchParameters(Action):
    def name(self) -> str:
        return "action_show_search_parameters"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", [])
        idx = utils.get_slot(tracker, "selected_searches")[0]
        search = utils.get_kv_store()[history[idx]]

        parameters = search.get("parameters", {})
        if "place_type" in parameters:
            place_type = utils.singularize(parameters["place_type"])
        elif parameters.get("activity") == "eat":
            place_type = "place where to eat"
        elif parameters.get("activity") == "drink":
            place_type = "place where to drink"
        else:
            place_type = "place"

        msg = "Here are the search details:\n"
        if "place_name" in parameters:
            place_name = parameters["place_name"]
            location = parameters["location"]["short_formatted_address"]
            msg += (
                f"- you are looking for a {place_type} called {place_name} "
                f"near {location}"
            )
        else:
            cusine_type = parameters.get("cuisine_type")
            meal_type = parameters.get("meal_type")
            msg += f"- you are looking for a {place_type}"
            if meal_type is not None:
                msg += f" for {meal_type}"
            if cusine_type is not None:
                msg += f" with {cusine_type} cuisine"

            location = parameters["location"]["short_formatted_address"]
            msg += f" near {location}"

        ranking = parameters.get("rank_by", "relevance")
        msg += f"\n- the results are ranked by {ranking}"
        dispatcher.utter_message(msg)

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
        search = store[history[idx]]
        prev_results = search.get("results")

        results = await utils.find_places(search["parameters"])
        if len(results) == 0:
            if prev_results is None:
                msg = "I couldn't find any places matching your search criteria. "
                msg += "Try loosening them a bit."
            elif len(prev_results) == 0:
                msg = "Sorry, but I still cannot find any places."
            else:
                msg = "These new search criteria may be too restrictive because I "
                msg += "cannot find any places satisfying them."
        elif len(results) == 1:
            if prev_results is None:
                msg = "I found only one place matching your search criteria: "
                msg += utils.get_place_title(results[0])
            elif len(prev_results) == 0:
                msg = "Well at least now I found one place: "
                msg += utils.get_place_title(results[0])
            elif len(prev_results) == 1:
                msg = "Even now, I found only one place: "
                msg += utils.get_place_title(results[0])
            else:
                msg = "Using these new search criteria, I found only one place: "
                msg += utils.get_place_title(results[0])
        elif len(results) <= _PAGE_SIZE:
            if prev_results is None:
                msg = "Here are all the results I found:\n"
                for i, result in enumerate(results, start=1):
                    msg += f"{i}. {utils.get_place_title(result)}\n"
            elif len(prev_results) < len(results):
                msg = "With these new search criteria, I found more results:\n"
                for i, result in enumerate(results, start=1):
                    msg += f"{i}. {utils.get_place_title(result)}\n"
            else:
                msg = "Here are all the results I found with the new search criteria:\n"
                for i, result in enumerate(results, start=1):
                    msg += f"{i}. {utils.get_place_title(result)}\n"
        else:  # noqa: PLR5501
            if prev_results is None:
                msg = "I found multiple places matching your search criteria. "
                msg += f"Here are the top {_PAGE_SIZE}:\n"
                for i, result in enumerate(results[:_PAGE_SIZE], start=1):
                    msg += f"{i}. {utils.get_place_title(result)}\n"
            elif len(prev_results) < len(results):
                msg = f"Now I found many more places. Here are the top {_PAGE_SIZE}:\n"
                for i, result in enumerate(results[:_PAGE_SIZE], start=1):
                    msg += f"{i}. {utils.get_place_title(result)}\n"
            else:
                msg = f"Here are the new top {_PAGE_SIZE} results:\n"
                for i, result in enumerate(results[:_PAGE_SIZE], start=1):
                    msg += f"{i}. {utils.get_place_title(result)}\n"

        dispatcher.utter_message(msg)
        search["results"] = utils.serialize_iterable(results)
        store[history[idx]] = search

        return [SlotSet("selected_results", list(range(min(len(results), _PAGE_SIZE))))]


@utils.handle_action_exceptions
class RankResults(Action):
    """Action to rank the search results."""

    def name(self) -> str:
        return "action_rank_results"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        rank_by = None
        for intent in utils.get_intents(tracker):
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
        search = store[history[idx]]

        prev_rank_by = search["parameters"].get("rank_by", "relevance")
        if prev_rank_by == rank_by:
            dispatcher.utter_message(
                response="utter_already_ranked_by",
                rank_by=rank_by,
            )
            return []

        search["parameters"]["rank_by"] = rank_by

        prev_results = search.get("results", [])
        if len(prev_results) < 2:
            store[history[idx]] = search
            dispatcher.utter_message(response="utter_changed_rank_by", rank_by=rank_by)
            return []

        results = await utils.find_places(search["parameters"], start_new_search=False)
        if len(results) <= _PAGE_SIZE:
            # there are no more results to retrieve
            msg = f"Here are all the results sorted by {rank_by}:"
        else:
            # there are more results to retrieve
            msg = f"Here are the top {_PAGE_SIZE} results sorted by {rank_by}:"
        for i, result in enumerate(results[:_PAGE_SIZE], start=1):
            msg += f"\n{i}. {utils.get_place_title(result)}"

        dispatcher.utter_message(msg)
        search["results"] = utils.serialize_iterable(results)
        store[history[idx]] = search

        return [SlotSet("selected_results", list(range(min(len(results), _PAGE_SIZE))))]


@utils.handle_action_exceptions
class SetSelectedResults(Action):
    """Action to set the selected results."""

    def name(self) -> str:
        return "action_set_selected_results"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", [])
        idx = utils.get_slot(tracker, "selected_searches")[0]
        search = utils.get_kv_store()[history[idx]]

        if len(search.get("results", [])) == 0:
            return [
                SlotSet("selected_results", None),
                SlotSet("selected_results_error", "no_results"),
            ]

        mentions = utils.get_entity_values(tracker, "mention")
        if not mentions:
            selected = utils.get_slot(tracker, "selected_results")
            if selected is None:
                results = search.get("results", [])
                selected = list(range(min(len(results), _PAGE_SIZE)))

            return [
                SlotSet("selected_results", selected),
                SlotSet("selected_results_error", None),
            ]

        selected, errors = await utils.resolve_mentions(
            tracker,
            selected=utils.get_slot(tracker, "selected_results", []),
            num_entities=len(search.get("results", [])),
            entity_type=["result", "place"],
        )

        if errors:
            msg = "Sorry, but " + utils.join(errors, sep=", ", last_sep=" and ") + ".\n"
            dispatcher.utter_message(text=msg)
            return [SlotSet("selected_results_error", "wrong_indices")]

        return [
            SlotSet("selected_results", selected),
            SlotSet("selected_results_error", None),
        ]


@utils.handle_action_exceptions
class ShowSelectedResults(Action):
    """Action to show the selected search results to the user."""

    def name(self) -> str:
        return "action_show_selected_results"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "search_history", [])
        idx = utils.get_slot(tracker, "selected_searches")[0]
        search = utils.get_kv_store()[history[idx]]

        results = search.get("results", [])
        selected = utils.get_slot(tracker, "selected_results")

        results = [results[i] for i in selected]
        results = utils.deserialize_iterable(places.Place, results)
        if len(results) == 1:
            place = results[0]
            msg = f"Here is the selected result:\n{utils.get_place_title(place)}"
        else:
            msg = "Here are the selected results:\n"
            for i, result in zip(selected, results, strict=True):
                msg += f"{i + 1}. {utils.get_place_title(result)}\n"

        dispatcher.utter_message(msg)

        return []
