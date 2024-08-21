# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime, time
from typing import Any

from gcp.maps import places
from geopy import distance
from rasa_sdk import Action, Tracker
from rasa_sdk.events import FollowupAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from . import utils


@utils.handle_action_exceptions
class RetrievePlaceInfo(Action):
    """Retrieves information about a place."""

    def name(self) -> str:
        return "action_retrieve_place_info"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        intents, entities = _get_intents(tracker)

        history = utils.get_slot(tracker, "search_history")
        idx = utils.get_slot(tracker, "selected_searches")[0]
        search = utils.get_kv_store().get_search(history[idx])

        selected: list[int] = utils.get_slot(tracker, "selected_results")
        if search.results is None:
            msg = "search.results is None"
            raise RuntimeError(msg)

        results = [search.results[i] for i in selected]

        msg = ""
        for place in results:
            if len(results) > 1:
                msg += "- "
            for idx, intent in enumerate(intents):
                if idx > 0:
                    if idx == len(utils.get_last_intents(tracker)) - 1:
                        msg += " and "
                    else:
                        msg += ", "

                # use the name of the place instead of the pronoun if
                # it's the first information to be provided and such information
                # is asked for multiple places
                name = place.display_name if idx == 0 else None
                name = name.text if name else None

                msg += await INTENT_TO_INFO[intent](place, name, entities)
            msg += "\n"

        dispatcher.utter_message(text=msg)
        if len(selected) == 1 and utils.get_slot(tracker, "suggest_booking"):
            place = results[0]
            if place.reservable:
                return [FollowupAction("action_suggest_booking")]

        return []


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #


def _get_intents(tracker: Tracker) -> tuple[list[str], list[dict[str, Any]]]:
    """Returns the intents that triggered the action."""
    valid_intents = set(INTENT_TO_INFO.keys())

    retrieve_event = None
    for event in reversed(tracker.events):
        if event["event"] != "user":
            continue

        intent = event["parse_data"]["intent"]["name"]
        if set(intent.split("+")) & valid_intents:
            retrieve_event = event
            break

    if retrieve_event is None:
        msg = "Invoked action_retrieve_place_info without a proper intent."
        raise RuntimeError(msg)

    intents = retrieve_event["parse_data"]["intent"]["name"].split("+")
    intents = [intent for intent in intents if intent in valid_intents]

    entities = retrieve_event["parse_data"]["entities"]

    return intents, entities


async def _get_address(place: places.Place, name: str | None, *_args: Any) -> str:
    address = place.short_formatted_address
    msg = f"the address of {name} is {address}" if name else f"its address is {address}"
    return msg


async def _get_contact(place: places.Place, name: str | None, *_args: Any) -> str:
    name = name or "it"
    contact = place.national_phone_number
    if contact is None:
        msg = f"unfortunately, I couldn't find a contact number for {name}"
    else:
        msg = f"you can contact {name} at {contact}"

    return msg


async def _get_price_level(place: places.Place, name: str | None, *_args: Any) -> str:
    name = name or "it"
    match place.price_level:
        case None | places.PriceLevel.UNSPECIFIED:
            msg = f"unfortunately, I couldn't find a price level for {name}"
        case places.PriceLevel.FREE:
            msg = f"{name} is free"
        case places.PriceLevel.INEXPENSIVE:
            msg = f"{name} is cheap"
        case places.PriceLevel.MODERATE:
            msg = f"{name} is moderately priced"
        case places.PriceLevel.EXPENSIVE:
            msg = f"{name} is expensive"
        case places.PriceLevel.VERY_EXPENSIVE:
            msg = f"{name} is very expensive"

    return msg


async def _get_rating(place: places.Place, name: str | None, *_args: Any) -> str:
    name = name or "it"
    rating = place.rating
    if rating is None:
        msg = f"unfortunately, I couldn't find a rating for {name}"
    else:
        msg = f"{name} has a rating of {rating} out of 5"

    return msg


async def _get_website(place: places.Place, name: str | None, *_args: Any) -> str:
    website = place.website_uri
    if website is None:
        name = name or "it"
        msg = f"unfortunately, I couldn't find a website for {name}"
    else:
        name = f"{name}'s" if name else "its"
        msg = f"you can visit {name} website at {website}"

    return msg


async def get_allows_animals(place: places.Place, name: str | None, *_args: Any) -> str:
    name = name or "it"
    match place.allows_dogs:
        case None:
            msg = f"unfortunately, I couldn't find any information about whether {name}"
            msg += " allows animals"
        case True:
            msg = f"animals are allowed at {name}"
        case False:
            msg = f"unfortunately, {name} doesn't allow animals"

    return msg


async def _get_good_for_children(
    place: places.Place,
    name: str | None,
    *_args: Any,
) -> str:
    name = name or "it"
    good_for_children = place.good_for_children
    menu_for_children = place.menu_for_children
    match (good_for_children, menu_for_children):
        case (True, None) | (True, False):
            msg = f"{name} is good for children"
        case (None, True) | (False, True):
            msg = f"{name} offers a dedicated menu for children"
        case (True, True):
            msg = f"{name} is good for children and it even offers a dedicated menu "
            msg += "for them"
        case (False, False) | (False, None) | (None, False):
            msg = f"it seems that {name} is not ideal for children"
        case _:
            msg = "unfortunately, I couldn't find any information about whether "
            msg += f"{name} is ideal for children"

    return msg


async def _get_parking_options(
    place: places.Place,
    name: str | None,
    *_args: Any,
) -> str:
    name = name or "it"
    options = place.parking_options
    if options is None:
        msg = "unfortunately, I couldn't find any information about the parking options"
        msg += f" near {name}"
    elif options.free_garage_parking or options.free_parking_lot:
        msg = f"{name} provides free parking to its customers"
    elif options.free_street_parking:
        msg = f"you can park for free on the street near {name}"
    elif options.paid_garage_parking or options.paid_parking_lot:
        msg = f"{name} provides paid parking to its customers"
    elif options.paid_street_parking:
        msg = f"you can park for a fee on the street near {name}"
    elif place.location:
        parkings = await utils.find_parkings(place.location)
        if parkings:
            dist = distance.distance(place.location, parkings[0].location).m
            msg = f"the nearest parking option is {dist:.0f} meters away from {name}"
        else:
            msg = f"there are no parking options near {name}"
    else:
        msg = "unfortunately, I couldn't find any information about the parking options"
        msg += f" near {name}"

    return msg


async def _get_payment_options(
    place: places.Place,
    name: str | None,
    *_args: Any,
) -> str:
    name = name or "it"
    options = place.payment_options
    if options is None:
        msg = "unfortunately, I couldn't find any information about the payment options"
        msg += f" {name} accepts"
        return msg

    if options.accepts_cash_only:
        msg = f"{name} only accepts cash"
    else:
        msg = f"you can pay both in cash and with a card at {name}"

    return msg


async def _get_outdoor_seating(
    place: places.Place,
    name: str | None,
    *_args: Any,
) -> str:
    name = name or "it"
    match place.outdoor_seating:
        case None:
            msg = f"unfortunately, I couldn't find any information about whether {name}"
            msg += " offers outdoor seating"
        case True:
            msg = f"{name} offers outdoor seating"
        case False:
            msg = f"{name} doesn't have any outdoor seating"

    return msg


async def _get_reservable(place: places.Place, name: str | None, *_args: Any) -> str:
    name = name or "it"
    match place.reservable:
        case None:
            msg = f"unfortunately, I couldn't find any information about whether {name}"
            msg += " can be reserved"
        case True:
            msg = f"{name} accepts reservations"
        case False:
            msg = f"unfortunately, {name} doesn't accept reservations"

    return msg


async def _get_restroom(place: places.Place, name: str | None, *_args: Any) -> str:
    name = name or "it"
    match place.restroom:
        case None:
            msg = f"unfortunately, {name} doesn't declare whether it has a restroom"
        case True:
            msg = f"{name} has a restroom"
        case False:
            msg = f"{name} doesn't have a restroom"

    return msg


async def _get_vegetarian(place: places.Place, name: str | None, *_args: Any) -> str:
    name = name or "it"
    match place.serves_vegetarian_food:
        case None:
            msg = f"unfortunately, {name} doesn't provide any information about the "
            msg += "vegetarian options it offers"
        case True:
            msg = f"{name} serves vegetarian food"
        case False:
            msg = f"{name} doesn't have any vegetarian options"

    return msg


async def _get_takeout(place: places.Place, name: str | None, *_args: Any) -> str:
    name = name or "it"
    match place.takeout:
        case None:
            msg = "unfortunately, I couldn't find any information about whether "
            msg += f"{name} offers takeout"
        case True:
            msg = f"{name} offers takeout"
        case False:
            msg = f"{name} doesn't offer takeout"

    return msg


async def _get_opening_hours(  # noqa: C901, PLR0912, PLR0915
    place: places.Place,
    name: str | None,
    entities: list[dict[str, Any]],
) -> str:
    if place.regular_opening_hours is None:
        msg = f"unfortunately, it seems that {name} doesn't provide any information "
        msg += "about its opening hours"
        return msg

    name = name or "it"
    datetimes: list[utils.Time] = []
    for entity in entities:
        if entity["entity"] == "datetime":
            datetimes.extend(await utils.parse_times(entity["value"]))

    now = datetime.now()  # noqa: DTZ005

    if len(datetimes) == 0:
        msg = ""
        for i in range(7):
            msg += _get_day_schedule(place, i, name)
            msg += "\n"
            name = "it"
        return msg

    msg = ""
    for t in datetimes:
        match t:
            case utils.Instant(value, grain):
                start, end = value, None
            case utils.Interval(start, end):
                grain = start.grain
                start = start.value
                end = end.value if end else None

        if end is None:
            is_open = utils.is_place_open(place, start)
            if grain in ["second", "minute", "hour"]:
                if now.date() == start.date():
                    if now.hour == start.hour:
                        msg += f"right now, {name} is"
                    elif now.hour < start.hour:
                        msg += f"today at {start.strftime('%I:%M %p')}, {name} will be"
                    else:
                        msg += f"today at {start.strftime('%I:%M %p')}, {name} was"
                elif now.date() < start.date():
                    msg += f"on {start.strftime('%A %d %B %Y')}, {name} will be"
                else:
                    msg += f"on {start.strftime('%A %d %B %Y')}, {name} was"

                msg += " open" if is_open else " closed"
            elif grain == "day":
                msg += _get_day_schedule(place, start.weekday(), name)
                name = "it"
            else:
                for idx in range(7):
                    msg += _get_day_schedule(place, idx, name)
                    msg += "\n"
                    name = "it"
        elif grain in ["second", "minute", "hour"]:
            intervals = _get_intervals(place, start, end)
            if len(intervals) == 0:
                if now.date() == start.date():
                    msg += f"today, {name} is closed from {start.strftime('%I:%M %p')} "
                    msg += f"to {end.strftime('%H:%M')}"
                elif now.date() < start.date():
                    msg += f"on {start.strftime('%A %d %B %Y')}, {name} will be closed "
                    msg += (
                        f"from {start.strftime('%H:%M')} to {end.strftime('%I:%M %p')}"
                    )
                else:
                    msg += f"on {start.strftime('%A %d %B %Y')}, {name} was closed "
                    msg += (
                        f"from {start.strftime('%H:%M')} to {end.strftime('%I:%M %p')}"
                    )
            else:
                if now.date() == start.date():
                    msg += f"today, {name} is open from "
                elif now.date() < start.date():
                    msg += (
                        f"on {start.strftime('%A %d %B %Y')}, {name} will be open from "
                    )
                else:
                    msg += f"on {start.strftime('%A %d %B %Y')}, {name} was open from "

                for idx, (s, e) in enumerate(intervals):
                    if idx > 0:
                        if idx == len(intervals) - 1:
                            msg += " and "
                        else:
                            msg += ", "

                    msg += f"{s.strftime('%I:%M %p')} to {e.strftime('%I:%M %p')}"
        elif grain == "day":
            for i in range(start.weekday(), end.weekday() + 1):
                msg += _get_day_schedule(place, i, name)
                msg += "\n"
        else:
            for i in range(7):
                msg += _get_day_schedule(place, i, name)
                msg += "\n"

        name = "it"
        # not all if set a new line character at the end of the message
        # so, to be safe, we remove it if it's there and add it back
        msg = msg.strip("\n")
        msg += "\n"

    return msg.strip("\n")


def _get_day_schedule(place: places.Place, wd: int, name: str) -> str:
    if place.regular_opening_hours is None:
        raise RuntimeError

    day = WEEKDAYS[wd]
    periods = place.regular_opening_hours.periods[wd]
    # If the place opens the day before and closes at 00:00, the periods list
    # will contain a tuple (None, 00:00) for the current day.
    # However, we do not want to say that for the current day the place is open
    # until 00:00 (the user may think that the place is open for 24 hours),
    # so we remove it.
    periods = [(s, e) for s, e in periods if s is not None or e != time(0, 0)]
    if len(periods) == 0:
        return f"on {day}, {name} is closed"

    msg = ""
    for idx, (start, end) in enumerate(periods):
        if idx == 0:
            msg += f"on {day}, {name} is open "
        elif idx == len(periods) - 1:
            msg += " and "
        else:
            msg += ", "

        match start, end:
            case None, None:
                msg = "all day"
            case None, _:
                msg += f"until {end.strftime('%I:%M %p')}"  # type: ignore
            case _, None:
                msg += f"{start.strftime('%I:%M %p')}"
            case _:
                msg += f"from {start.strftime('%I:%M %p')} "
                msg += f"to {end.strftime('%I:%M %p')}"

    return msg


def _get_intervals(  # noqa: C901, PLR0912
    place: places.Place,
    start: datetime,
    end: datetime,
) -> list[tuple[time, time]]:
    if place.regular_opening_hours is None:
        raise RuntimeError

    periods = place.regular_opening_hours.periods[start.weekday()]
    if len(periods) == 0:
        return []

    if periods[0] == (None, None):
        return [(start.time(), end.time())]

    intervals = []
    for s, e in periods:
        match s, e:
            case None, None:
                continue
            case None, _:
                assert e is not None  # noqa: S101
                if e < start.time():
                    continue
                if e > end.time():
                    intervals.append((start.time(), end.time()))
                else:
                    intervals.append((start.time(), e))
            case _, None:
                assert s is not None  # noqa: S101
                if s > end.time():
                    continue
                if s < start.time():
                    intervals.append((start.time(), end.time()))
                else:
                    intervals.append((s, end.time()))
            case _:
                if e < start.time() or s > end.time():
                    continue
                s = max(s, start.time())  # noqa: PLW2901
                e = min(e, end.time())  # noqa: PLW2901
                intervals.append((s, e))

    return intervals


INTENT_TO_INFO = {
    "ask_address": _get_address,
    "ask_contact": _get_contact,
    "ask_price_level": _get_price_level,
    "ask_rating": _get_rating,
    "ask_website": _get_website,
    "ask_allows_animals": get_allows_animals,
    "ask_good_for_children": _get_good_for_children,
    "ask_parking_options": _get_parking_options,
    "ask_payment_options": _get_payment_options,
    "ask_outdoor_seating": _get_outdoor_seating,
    "ask_reservable": _get_reservable,
    "ask_restroom": _get_restroom,
    "ask_vegetarian": _get_vegetarian,
    "ask_takeout": _get_takeout,
    "ask_opening_hours": _get_opening_hours,
}


WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
