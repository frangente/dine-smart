# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import gcp.maps
import rapidfuzz
from gcp.maps import places
from geopy import distance

from ._grammar import pluralize
from ._misc import deserialize

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

_ALTERNATIVE_PARAMETERS = [
    "activity",
    "meal_type",
    "cuisine_type",
    "place_type",
    "place_name",
]
_LOCATION_FIELDS = ["id", "viewport", "short_formatted_address"]
_PLACE_FIELDS = [
    "display_name",
    "primary_type_display_name",
    "short_formatted_address",
]
_USER_LOCATION_EXAMPLES = {
    "my location",
    "my position",
    "my coordinates",
    "my address",
    "my place",
    "my home",
    "my city",
    "my town",
    "where i am",
    "where i live",
    "where i stay",
    "where i reside",
}

_client = gcp.maps.Client()

# --------------------------------------------------------------------------- #
# Search parameters
# --------------------------------------------------------------------------- #


def get_search_title(parameters: dict[str, Any]) -> str:
    """Generates a title for the search."""
    location = parameters["location"]["short_formatted_address"]
    if parameters.get("place_name"):
        title = f"search for {parameters['place_name']}"
        if location:
            title += f" near {location}"
    else:
        activity = parameters.get("activity")
        place_type = parameters.get("place_type")
        meal_type = parameters.get("meal_type")
        cuisine_type = parameters.get("cuisine_type")

        if place_type:
            place_type = pluralize(place_type)
        elif activity == "eat":
            place_type = "places to eat"
        elif activity == "drink":
            place_type = "places to have a drink"
        else:
            place_type = "places"

        title = "search for "
        if cuisine_type:
            title += f"{cuisine_type} "
        title += f"{place_type}"

        if meal_type:
            title += f" for {meal_type}"
        title += f" near {location}"

    return title


def get_place_title(place: places.Place) -> str:
    """Returns the title of the place to be displayed to the user."""
    name = place.display_name.text if place.display_name else ""
    address = place.short_formatted_address or ""
    title = f"{name} ({address})"

    return title


def validate_search_parameters(
    params: dict[str, Any],
    *,
    include_location: bool = True,
) -> bool:
    """Checks if the required parameters are present in the search."""
    if include_location and "location" not in params:
        return False

    return any(params.get(p) for p in _ALTERNATIVE_PARAMETERS)


# --------------------------------------------------------------------------- #
# Find locations
# --------------------------------------------------------------------------- #


def is_user_location(text: str) -> bool:
    """Checks if the text is a user-like location."""
    return text.lower() in _USER_LOCATION_EXAMPLES


async def find_location(
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
    locations, _ = await _client.search_places_by_text(
        query=query,
        fields=_LOCATION_FIELDS,
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


def merge_locations(*args: str) -> str:
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


async def find_parkings(
    location: places.LatLng,
    max_distance: int = 500,
) -> list[places.Place]:
    """Finds parkings near the given location."""
    parkings = await _client.search_nearby_places(
        area=places.CircularArea(location, max_distance),
        fields=["location"],
        included_primary_types=["parking"],
        max_num_results=1,
        rank_by="distance",
    )

    return parkings


# --------------------------------------------------------------------------- #
# Search for places
# --------------------------------------------------------------------------- #


async def find_places(
    parameters: dict[str, Any],
    *,
    start_new_search: bool = True,
    return_n: int = 20,
) -> list[places.Place]:
    """Searches for places using the Google Places API.

    Args:
        parameters: The search parameters.
        start_new_search: Whether to start a new search or continue from the previous
            search results.
        return_n: The maximum number of results to return.

    Returns:
        A list of places matching the search criteria.
    """
    location = deserialize(places.Place, parameters["location"])

    place_name = parameters.get("place_name")
    place_type = parameters.get("place_type")
    cuisine_type = parameters.get("cuisine_type")
    meal_type = parameters.get("meal_type")
    query = f"{place_name or ''} {cuisine_type or ''} {place_type or ''}"
    if query and meal_type:
        query += f" for {meal_type}"
    else:
        query = meal_type or query
    query = query.strip()

    activity = parameters.get("activity")
    match activity:
        case "eat":
            query = "places to eat"
        case "drink":
            query = "places to drink"
        case _:
            pass

    rank_by = parameters.get("rank_by", "relevance")
    open_now = parameters.get("open_now", False)
    price_levels = _get_price_levels(parameters.get("price_range"))
    min_rating = _get_min_rating(parameters.get("quality"))

    next_page_token = None if start_new_search else parameters.get("next_page_token")

    results = []
    while len(results) < return_n:
        page_size = min(20, return_n - len(results))
        res, next_page_token = await _client.search_places_by_text(
            query=query,
            fields=_PLACE_FIELDS,
            bias_area=location.viewport,
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

    return results


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
