# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import rapidfuzz
from gcp.maps import places
from geopy import distance
from rasa_sdk import Action, FormValidationAction, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import ValidationAction
from rasa_sdk.types import DomainDict

from rasa.shared.nlu.constants import ENTITY_ATTRIBUTE_VALUE

from . import utils
from ._constants import LOCATION_FIELDS, PAGE_SIZE, PLACE_FIELDS, USER_LOCATION_EXAMPLES

# --------------------------------------------------------------------------- #
# Form-related Actions
# --------------------------------------------------------------------------- #


@utils.handle_action_exceptions
class ValidateSearchForm(FormValidationAction):
    """Validates the search form."""

    def name(self) -> str:
        return "validate_search_form"

    async def required_slots(
        self,
        domain_slots: list[str],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[str]:
        search = utils.get_current_search(tracker)

        slots = {"place_type", "location"}

        if search.get("place_name"):
            slots.add("location")
        else:
            activity = search.get("activity")
            meal_type = search.get("meal_type")
            cuisine_type = search.get("cuisine_type")
            if any([activity, meal_type, cuisine_type]):
                slots.remove("place_type")

        if search.get("place_type"):
            slots.remove("place_type")
        if search.get("location"):
            slots.remove("location")

        if utils.get_slot(tracker, "invalid_place_type"):
            slots.add("place_type")

        if utils.get_slot(tracker, "invalid_location"):
            slots.add("location")

        return list(slots)

    async def extract_location(  # noqa: PLR0911
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> dict[str, Any]:
        user_location = utils.get_slot(tracker, "user_location")
        location = utils.get_entity_values(tracker, "location")
        if not location:
            if not utils.get_slot(tracker, "location"):
                return {}

            open_now = utils.get_current_search(tracker).get("open_now", False)
            if open_now and user_location:
                return {
                    "location": user_location,
                    "invalid_location": None,
                    "invalid_location_reasons": None,
                }

            return {}

        location = location[0]
        if location.lower() in USER_LOCATION_EXAMPLES:
            if not user_location:
                return {
                    "location": None,
                    "invalid_location": None,
                    "invalid_location_reasons": ["unknown_user_location"],
                }

            return {
                "location": user_location,
                "invalid_location": None,
                "invalid_location_reasons": None,
            }

        reasons = utils.get_slot(tracker, "invalid_location_reasons", [])
        fill_user_location = (
            "inform_my_location" in utils.get_intents(tracker)
            or "unknown_user_location" in reasons
        )
        if reasons and reasons[-1] == "ambiguous":
            # The user previously provided a location that was ambiguous and we asked
            # them to provide more information to disambiguate it. So, the new location
            # provided by the user should not be used to replace the old one, but we
            # should merge the two locations. For example, if the user previously said
            # "via Cavour" and now says "Rome", we should search for "via Cavour, Rome".
            invalid = utils.get_slot(tracker, "invalid_location")
            if invalid is None:
                msg = "invalid_location is None, but it should not be."
                raise RuntimeError(msg)

            location = _merge_locations(invalid, location)

        candidates = await _find_location(
            location,
            utils.deserialize(places.Place, user_location) if user_location else None,
        )
        if len(candidates) != 1:
            # the location provided is ambiguous or not found
            reasons += ["ambiguous" if candidates else "not_found"]
            return {
                "location": None,
                "invalid_location": location,
                "invalid_location_reasons": reasons,
            }

        location = utils.serialize(candidates[0])
        slots = {
            "location": location,
            "invalid_location": None,
            "invalid_location_reasons": None,
        }
        if fill_user_location:
            slots["user_location"] = location

        return slots

    async def extract_place_type(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> dict[str, Any]:
        types = utils.get_entities(tracker, "place_type")
        if not types:
            return {}

        if types[0].get("is_correct", True):
            place_type = types[0][ENTITY_ATTRIBUTE_VALUE]
        else:
            place_type = None

        return {
            "place_type": place_type,
            "invalid_place_type": True,
        }


@utils.handle_action_exceptions
class SetSearchParameters(ValidationAction):
    """Sets the search parameters based on the user's input."""

    async def extract_search_history(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> dict[str, Any]:
        history = utils.get_slot(tracker, "search_history", [])
        selected_searches = utils.get_slot(tracker, "selected_searches", [])
        if len(selected_searches) != 1:
            return {}

        parameters = {
            "place_name": await self._get_place_name(tracker),
            "open_now": await self._get_open_now(tracker),
            "activity": await self._get_activity(tracker),
            "cuisine_type": await self._get_cuisine_type(tracker),
            "price_range": await self._get_price_range(tracker),
            "quality": await self._get_quality(tracker),
        }
        parameters = {k: v for k, v in parameters.items() if v is not None}

        search = history[selected_searches[0]]
        if any(p != search.get(k) for k, p in parameters.items()):
            history = history.copy()
            search = search.copy()
            search.update(parameters)
            history[selected_searches[0]] = search
            return {"search_history": history}

        return {}

    async def validate_search_history(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> dict[str, Any]:
        # just to avoid the warning about the missing validation method
        return {"search_history": slot_value}

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
class AskForPlaceType(Action):
    """Asks the user for the place type."""

    def name(self) -> str:
        return "action_ask_place_type"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        invalid = utils.get_slot(tracker, "invalid_place_type", False)  # noqa: FBT003
        if invalid:
            dispatcher.utter_message(response="utter_invalid_place_type")
        else:
            dispatcher.utter_message(response="utter_ask_place_type")

        return []


@utils.handle_action_exceptions
class AskForLocation(Action):
    """Asks the user for the location."""

    def name(self) -> str:
        return "action_ask_location"

    async def run(  # noqa: PLR0912, C901
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        invalid = utils.get_slot(tracker, "invalid_location", None)
        reasons = utils.get_slot(tracker, "invalid_location_reasons", [])

        search = utils.get_current_search(tracker)
        place_type = utils.get_slot(tracker, "place_type")
        if place_type is not None:
            place_type = utils.pluralize(place_type)
        elif search.get("activity") == "eat":
            place_type = "places to eat"
        elif search.get("activity") == "drink":
            place_type = "places to have a drink"
        else:
            place_type = "places"

        if not reasons:
            # the user never provided a location for the search, but we may have
            # already asked them for their location
            asked_count = utils.count_action_inside_form(tracker, self.name())
            open_now = search.get("open_now", False)
            name = search.get("place_name")

            if asked_count > 2:
                # the user has been asked for the location multiple times, but they
                # never provided it, so we ask them if they want to stop the search
                dispatcher.utter_message(response="utter_ask_stop_search")
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
        history[idx] = history[idx].copy()

        location = utils.get_slot(tracker, "location")
        if location is not None:
            history[idx]["location"] = location

        place_type = utils.get_slot(tracker, "place_type")
        if place_type is not None:
            history[idx]["place_type"] = place_type

        store = utils.get_kv_store()
        prev_results = history[idx].get("results")
        if prev_results is not None:
            prev_results = store[prev_results]

        results, next_page_token = await _find_places(history[idx])
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
                msg += _get_place_title(results[0])
            elif len(prev_results) == 0:
                msg = "Well at least now I found one place: "
                msg += _get_place_title(results[0])
            elif len(prev_results) == 1:
                msg = "Even now, I found only one place: "
                msg += _get_place_title(results[0])
            else:
                msg = "Using these new search criteria, I found only one place: "
                msg += _get_place_title(results[0])
        elif len(results) <= PAGE_SIZE and next_page_token is None:
            if prev_results is None:
                msg = "Here are all the results I found:\n"
                for i, result in enumerate(results, start=1):
                    msg += f"{i}. {_get_place_title(result)}\n"
            elif len(prev_results) < len(results):
                msg = "With these new search criteria, I found more results:\n"
                for i, result in enumerate(results, start=1):
                    msg += f"{i}. {_get_place_title(result)}\n"
            else:
                msg = "Here are all the results I found with the new search criteria:\n"
                for i, result in enumerate(results, start=1):
                    msg += f"{i}. {_get_place_title(result)}\n"
        else:  # noqa: PLR5501
            if prev_results is None:
                msg = "I found multiple places matching your search criteria. "
                msg += f"Here are the top {PAGE_SIZE}:\n"
                for i, result in enumerate(results[:PAGE_SIZE], start=1):
                    msg += f"{i}. {_get_place_title(result)}\n"
            elif len(prev_results) < len(results):
                msg = f"Now I found many more places. Here are the top {PAGE_SIZE}:\n"
                for i, result in enumerate(results[:PAGE_SIZE], start=1):
                    msg += f"{i}. {_get_place_title(result)}\n"
            else:
                msg = f"Here are the new top {PAGE_SIZE} results:\n"
                for i, result in enumerate(results[:PAGE_SIZE], start=1):
                    msg += f"{i}. {_get_place_title(result)}\n"

        dispatcher.utter_message(msg)

        history[idx]["results"] = store.add(utils.serialize_iterable(results))
        history[idx]["next_page_token"] = next_page_token
        if not history[idx].get("title_given_by_user", False):
            history[idx]["title"] = _generate_search_title(history[idx])
            history[idx]["title_given_by_user"] = False

        return [SlotSet("search_history", history)]


@utils.handle_action_exceptions
class RankResults(Action):
    """Action to rank the search results."""

    def name(self) -> str:
        return "action_rank_results"

    async def run(  # noqa: C901
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

        prev_rank_by = history[idx].get("rank_by", "relevance")
        if prev_rank_by == rank_by:
            dispatcher.utter_message(
                response="utter_already_ranked_by",
                rank_by=rank_by,
            )
            return []

        store = utils.get_kv_store()
        history = history.copy()
        history[idx] = history[idx].copy()
        history[idx]["rank_by"] = rank_by

        prev_results = history[idx].get("results")
        if prev_results is None:
            dispatcher.utter_message(response="utter_changed_rank_by", rank_by=rank_by)
            return []

        prev_results = store[prev_results]
        if len(prev_results) < 2:
            dispatcher.utter_message(response="utter_changed_rank_by", rank_by=rank_by)
            return []

        results, npt = await _find_places(history[idx], start_new_search=False)
        if len(results) <= PAGE_SIZE and npt is None:
            # there are no more results to retrieve
            msg = f"Here are all the results sorted by {rank_by}:"
        else:
            # there are more results to retrieve
            msg = f"Here are the top {PAGE_SIZE} results sorted by {rank_by}:"
        for i, result in enumerate(results[:PAGE_SIZE], start=1):
            msg += f"\n{i}. {_get_place_title(result)}"

        dispatcher.utter_message(msg)

        history[idx]["results"] = store.add(utils.serialize_iterable(results))
        history[idx]["next_page_token"] = npt

        return [SlotSet("search_history", history)]


# --------------------------------------------------------------------------- #
# Helper Functions
# --------------------------------------------------------------------------- #


async def _find_location(
    query: str,
    bias: places.Place | None,
    min_distance: float | None = 1000,
) -> list[places.Place]:
    """Finds locations matching the given text.

    This function uses the Google Maps Places API to search for locations matching
    the given text. If multiple locations are found, they are pruned to keep only
    those that are at least `min_distance` meters apart. This is useful to avoid
    showing multiple locations that can be considered the same, for example locations
    corresponding to the same street but with different house numbers.

    Args:
        query: The text to search for.
        bias: The viewport to bias the search to.
        min_distance: The minimum distance (in meters) between locations to consider
            them different. If `None`, no pruning is done.

    Returns:
        A list of locations matching the given text.
    """
    client = utils.get_maps_client()
    locations, _ = await client.search_places_by_text(
        query=query,
        fields=LOCATION_FIELDS,
        page_size=5,
        bias_area=bias.viewport if bias else None,
    )

    if min_distance is not None:

        def close(a: places.Place, b: places.Place) -> bool:
            return distance.distance(a.location, b.location).meters < min_distance

        groups: list[list[places.Place]] = []
        for location in locations:
            for group in groups:
                if any(close(location, loc) for loc in group):
                    group.append(location)
                    break
            else:
                groups.append([location])

        locations = [
            min(group, key=lambda loc: len(loc.short_formatted_address))  # type: ignore
            for group in groups
        ]

    return locations


def _merge_locations(*args: str) -> str:
    """Merges multiple locations into a single string.

    Given a list of strings representing parts of a location, this function
    merges them into a single string containing the full location.

    Args:
        *args: The parts of the location.

    Returns:
        The full location.

    Example:
        >>> merge_locations("via Cavour", "Rome")
        "via Cavour Rome"
        >>> merge_locations("via Cavour 16 Rome", "Rome Italy")
        "via Cavour 16 Rome Italy"
        >>> merge_locations("via Cavour Rome", "via Cavour 16 Rome")
        "via Cavour 16 Rome"
    """
    if len(args) != 2:
        msg = "Currently, only two locations can be merged."
        raise NotImplementedError(msg)

    x, y = args
    result = []
    cutoff = 80
    scorer = rapidfuzz.fuzz.ratio

    x_parts, y_parts = x.split(), y.split()
    x_idx, y_idx = 0, 0
    while x_idx < len(x_parts) and y_idx < len(y_parts):
        x_part, y_part = x_parts[x_idx], y_parts[y_idx]
        similarity = scorer(x_part, y_part)
        if similarity >= cutoff:
            result.append(x_part)
            x_idx += 1
            y_idx += 1
        else:
            # now we need to find the index in x and y
            # from which they are similar again
            best_match, x_match, y_match = cutoff, len(x_parts), len(y_parts)
            for i in range(x_idx, len(x_parts)):
                for j in range(y_idx, len(y_parts)):
                    ratio = scorer(x_parts[i], y_parts[j])
                    if ratio > best_match:
                        best_match, x_match, y_match = ratio, i, j

            # add the parts that are not similar
            result.extend(x_parts[x_idx:x_match])

            # add all parts from y that are not present in x
            for i in range(y_idx, y_match):
                is_matched = rapidfuzz.process.extractOne(
                    y_parts[i],
                    x_parts,
                    score_cutoff=cutoff,
                    scorer=scorer,
                    processor=rapidfuzz.utils.default_process,
                )
                if not is_matched:
                    result.append(y_parts[i])

            x_idx, y_idx = x_match, y_match

    # add the remaining parts
    result.extend(x_parts[x_idx:])
    result.extend(y_parts[y_idx:])

    return " ".join(result)


async def _find_places(
    search: dict[str, Any],
    *,
    start_new_search: bool = True,
    return_n: int = PAGE_SIZE,
) -> tuple[list[places.Place], str | None]:
    """Searches for places using the Google Places API.

    Args:
        search: The search parameters.
        start_new_search: Whether to start a new search or continue from the previous
            search results.
        return_n: The maximum number of results to return.

    Returns:
        A tuple containing the search results and the next page token to be used to
        retrieve more results.
    """
    location = search.get("location")
    if location is None:
        msg = "location is None, but it should not be."
        raise RuntimeError(msg)

    place_name = search.get("place_name")
    place_type = search.get("place_type")
    cuisine_type = search.get("cuisine_type")
    meal_type = search.get("meal_type")
    query = f"{place_name or ''} {cuisine_type or ''} {place_type or ''}"
    if query and meal_type:
        query += f" for {meal_type}"
    else:
        query = meal_type or query

    activity = search.get("activity")
    match activity:
        case "eat":
            primary_type = "food"
        case "drink":
            primary_type = "bar"
        case _:
            primary_type = None

    rank_by = search.get("rank_by", "relevance")
    open_now = search.get("open_now", False)
    price_levels = _get_price_levels(search.get("price_range"))
    min_rating = _get_min_rating(search.get("quality"))

    next_page_token = None if start_new_search else search.get("next_page_token")

    client = utils.get_maps_client()
    results = []
    page_size = max(20, return_n)  # the API can return up to 20 results per page
    while len(results) < return_n:
        res, next_page_token = await client.search_places_by_text(
            query=query,
            fields=PLACE_FIELDS,
            included_type=primary_type,
            bias_area=utils.deserialize(places.Place, location).viewport,
            page_size=page_size,
            next_page_token=next_page_token,
            open_now=open_now,
            price_levels=price_levels,
            min_rating=min_rating,
            rank_by=rank_by,
        )

        results.extend(res)
        if not next_page_token:
            break

    return results, next_page_token


def _get_price_levels(price_level: str | None) -> list[places.PriceLevel] | None:
    match price_level:
        case "any":
            return None
        case "expensive":
            return [places.PriceLevel.EXPENSIVE, places.PriceLevel.VERY_EXPENSIVE]
        case "moderate":
            return [places.PriceLevel.MODERATE]
        case "inexpensive":
            return [places.PriceLevel.INEXPENSIVE]
        case None:
            return None
        case _:
            msg = f"Invalid price level: {price_level}"
            raise ValueError(msg)


def _get_min_rating(quality: str | None) -> float | None:
    match quality:
        case "any":
            return None
        case "excellent":
            return 4.5
        case "moderate":
            return 3.5
        case None:
            return None
        case _:
            msg = f"Invalid quality: {quality}"
            raise ValueError(msg)


def _generate_search_title(search: dict[str, Any]) -> str:
    """Generates a title for the search."""
    location = search["location"]["short_formatted_address"]
    if search.get("place_name"):
        title = f"search for {search['place_name']} near {location}"
    else:
        activity = search.get("activity")
        place_type = search.get("place_type")
        meal_type = search.get("meal_type")
        cuisine_type = search.get("cuisine_type")

        if place_type:
            place_type = utils.pluralize(place_type)
        elif activity == "eat":
            place_type = "places to eat"
        elif activity == "drink":
            place_type = "places to have a drink"
        else:
            place_type = "places"

        title = f"search for {cuisine_type or ''} {place_type}"
        if meal_type:
            title += f" for {meal_type}"
        title += f" near {location}"

    return title


def _get_place_title(place: places.Place) -> str:
    """Returns the title of the place to be displayed to the user."""
    name = place.display_name.text if place.display_name else ""
    address = place.short_formatted_address or ""
    title = f"{name} ({address})"

    return title
