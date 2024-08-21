# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime

import gcp.maps
import rapidfuzz
from gcp.maps import places
from geopy import distance

from actions.records import BookingParameters, SearchParameters

from ._grammar import pluralize

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

_LOCATION_FIELDS = [
    "viewport",
    "short_formatted_address",
]
_PLACE_FIELDS = [
    "display_name",
    "primary_type_display_name",
    "short_formatted_address",
    "national_phone_number",
    "price_level",
    "rating",
    "website_uri",
    "allows_dogs",
    "good_for_children",
    "menu_for_children",
    "parking_options",
    "payment_options",
    "outdoor_seating",
    "reservable",
    "restroom",
    "serves_vegetarian_food",
    "takeout",
    "regular_opening_hours",
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

_client: gcp.maps.Client | None = None


def _get_client() -> gcp.maps.Client:
    """Returns the Google Maps client."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = gcp.maps.Client()
    return _client


# --------------------------------------------------------------------------- #
# Search parameters
# --------------------------------------------------------------------------- #


def is_place_open(place: places.Place, dt: datetime) -> bool:
    """Checks if the place is open at the given time."""
    if place.regular_opening_hours is None:
        msg = "The place does not have regular opening hours."
        raise ValueError(msg)

    opening_hours = place.regular_opening_hours.periods[dt.weekday()]

    is_open = False
    for start, end in opening_hours:
        match start, end:
            case None, None:
                is_open = True
                break
            case None, _:
                if dt.time() < end:  # type: ignore
                    is_open = True
                    break
            case _, None:
                if dt.time() >= start:
                    is_open = True
                    break
            case _, _:
                if start <= dt.time() < end:
                    is_open = True
                    break

    return is_open


def get_search_title(parameters: SearchParameters) -> str:
    """Returns the title of the search to be displayed to the user."""
    if parameters.place_name:
        return (
            f"search for {parameters.place_name} near "
            f"{parameters.location.short_formatted_address}"
        )

    if parameters.place_type:
        place_type = pluralize(parameters.place_type)
    elif parameters.activity == "eat":
        place_type = "places to eat"
    elif parameters.activity == "drink":
        place_type = "places to have a drink"
    else:
        place_type = "places to go"

    title = "search for "
    if parameters.cuisine_type:
        title += f"{parameters.cuisine_type} "
    title += place_type

    if parameters.meal_type:
        title += f" for {parameters.meal_type}"

    title += f" near {parameters.location.short_formatted_address}"
    return title


def get_place_title(place: places.Place) -> str:
    """Returns the title of the place to be displayed to the user."""
    name = place.display_name.text if place.display_name else ""
    address = place.short_formatted_address or ""
    title = f"{name} ({address})"

    return title


def get_booking_title(parameters: BookingParameters) -> str:
    """Returns the title of the booking to be displayed to the user."""
    place_name = parameters.place.display_name.text  # type: ignore
    dt = parameters.date.strftime("%A, %B %d, %Y at %I:%M %p")
    num_people = parameters.num_people

    return f"reservation for {num_people} people at {place_name} on {dt}"


# --------------------------------------------------------------------------- #
# Find locations
# --------------------------------------------------------------------------- #


def is_user_location(text: str) -> bool:
    """Checks if the text is a user-like location."""
    text = text.lower()
    return any(phrase in text for phrase in _USER_LOCATION_EXAMPLES)


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
    client = _get_client()
    locations, _ = await client.search_places_by_text(
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
    client = _get_client()
    parkings = await client.search_nearby_places(
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


async def find_places(  # noqa: C901
    parameters: SearchParameters,
    return_n: int = 15,
) -> list[places.Place]:
    """Searches for places using the Google Places API.

    Args:
        parameters: The search parameters.
        return_n: The maximum number of results to return.

    Returns:
        A list of places matching the search criteria.
    """
    query = ""
    if parameters.place_name:
        query += parameters.place_name + " "
    if parameters.cuisine_type:
        query += parameters.cuisine_type + " "
    if parameters.place_type:
        query += parameters.place_type + " "

    if not query:
        query = "places"

    if parameters.meal_type:
        query += f" for {parameters.meal_type}"

    if parameters.activity == "eat":
        included_type = "restaurant"
    elif parameters.activity == "drink":
        included_type = "bar"
    else:
        included_type = None

    if query != "places":
        included_type = None

    results = []
    client = _get_client()
    while len(results) < return_n:
        page_size = min(20, return_n - len(results))
        res, next_page_token = await client.search_places_by_text(
            query=query,
            fields=_PLACE_FIELDS,
            included_type=included_type,
            bias_area=parameters.location.viewport,
            page_size=page_size,
            open_now=parameters.open_now or False,
            price_levels=parameters.get_price_levels(),
            min_rating=parameters.get_min_rating(),
            rank_by=parameters.rank_by,
        )

        results.extend(res)
        if not next_page_token:
            break

    return results
