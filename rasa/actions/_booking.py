# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime
from typing import Any

from gcp.maps import places
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from . import utils
from .records import BookingData, BookingParameters

# --------------------------------------------------------------------------- #
# Form-related Actions
# --------------------------------------------------------------------------- #


@utils.handle_action_exceptions
class SetBookingDateTime(Action):
    """Action that sets the date and time for a booking."""

    def name(self) -> str:
        return "action_set_booking_datetime"

    async def run(  # noqa: C901, PLR0911
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        entities = utils.get_entity_values(tracker, "datetime")
        if not entities:
            return []

        date = None
        for entity in entities:
            tmp = await utils.parse_times(entity)
            if tmp:
                date = tmp[0]
                break

        if date is None:
            return []

        match date:
            case utils.Instant(value, grain):
                date = value
            case utils.Interval(start, _):
                date, grain = start.value, start.grain

        today = datetime.now()  # noqa: DTZ005
        if date < today:
            return [
                SlotSet("booking_datetime", None),
                SlotSet("booking_datetime_error", "past"),
            ]

        if date.day > today.day + 28:
            return [
                SlotSet("booking_datetime", None),
                SlotSet("booking_datetime_error", "far"),
            ]

        if grain not in ["second", "minute", "hour"]:
            return [
                SlotSet("booking_datetime", None),
                SlotSet("booking_datetime_error", "coarse"),
            ]

        place = utils.get_slot(tracker, "booking_place")
        place = utils.deserialize(places.Place, place)

        if not utils.is_place_open(place, date):
            return [
                SlotSet("booking_datetime", None),
                SlotSet("booking_datetime_error", "closed"),
            ]

        return [
            SlotSet("booking_datetime", date.isoformat()),
            SlotSet("booking_datetime_error", None),
        ]


@utils.handle_action_exceptions
class SetBookingPeopleCount(Action):
    """Action that sets the number of people for a booking."""

    def name(self) -> str:
        return "action_set_booking_people_count"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        entities = utils.get_entity_values(tracker, "people_count")
        if not entities:
            return []

        counts = await utils.parse_numbers(entities[0])
        if not counts:
            return []

        count = counts[0]
        if count < 1:
            return [
                SlotSet("booking_people_count", None),
                SlotSet("booking_people_count_error", "small"),
            ]

        if count > 10:
            return [
                SlotSet("booking_people_count", None),
                SlotSet("booking_people_count_error", "large"),
            ]

        return [
            SlotSet("booking_people_count", count),
            SlotSet("booking_people_count_error", None),
        ]


@utils.handle_action_exceptions
class SetBookingAuthor(Action):
    """Action that sets the author for a booking."""

    def name(self) -> str:
        return "action_set_booking_author"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        requested_slot = utils.get_slot(tracker, "requested_slot")
        if requested_slot == "booking_author":
            intents = utils.get_last_intents(tracker)
            if "affirm" in intents:
                return [SlotSet("booking_author", utils.get_slot(tracker, "user_name"))]

        entities = utils.get_entity_values(tracker, "user_name")
        if not entities:
            return []

        return [SlotSet("booking_author", entities[0])]


@utils.handle_action_exceptions
class AskBookingDateTime(Action):
    """Action that asks for the date and time of a booking."""

    def name(self) -> str:
        return "action_ask_booking_datetime"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        error = utils.get_slot(tracker, "booking_datetime_error")
        match error:
            case None:
                dispatcher.utter_message(response="utter_ask_booking_datetime")
            case "coarse":
                dispatcher.utter_message(response="utter_ask_booking_datetime_coarse")
            case "past":
                dispatcher.utter_message(response="utter_ask_booking_datetime_past")
            case "far":
                dispatcher.utter_message(response="utter_ask_booking_datetime_far")
            case "closed":
                dispatcher.utter_message(response="utter_ask_booking_datetime_closed")
            case _:
                msg = "Unknown error: {error}"
                raise RuntimeError(msg)

        return []


@utils.handle_action_exceptions
class AskBookingPeopleCount(Action):
    """Action that asks for the number of people for a booking."""

    def name(self) -> str:
        return "action_ask_booking_people_count"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        error = utils.get_slot(tracker, "booking_people_count_error")

        dt = utils.get_slot(tracker, "booking_datetime")
        dt = datetime.fromisoformat(dt) if dt else None
        human_dt = dt.strftime("%A, %B %d, %Y at %I:%M %p") if dt else None
        match error:
            case None:
                dispatcher.utter_message(
                    response="utter_ask_booking_people_count", datetime=human_dt
                )
            case "small":
                dispatcher.utter_message(
                    response="utter_ask_booking_people_count_small"
                )
            case "large":
                dispatcher.utter_message(
                    response="utter_ask_booking_people_count_large"
                )
            case _:
                msg = "Unknown error: {error}"
                raise RuntimeError(msg)

        return []


@utils.handle_action_exceptions
class AskBookingAuthor(Action):
    """Action that asks for the author of a booking."""

    def name(self) -> str:
        return "action_ask_booking_author"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        user_name = utils.get_slot(tracker, "user_name")
        if user_name != "\b":
            dispatcher.utter_message(
                response="utter_ask_booking_author_with_name",
                user_name=user_name,
            )
        else:
            dispatcher.utter_message(response="utter_ask_booking_author")

        return []


# --------------------------------------------------------------------------- #
# Booking-related Actions
# --------------------------------------------------------------------------- #


@utils.handle_action_exceptions
class SuggestBooking(Action):
    """Action that suggests booking a place."""

    def name(self) -> str:
        return "action_suggest_booking"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        dispatcher.utter_message(response="utter_suggest_booking")
        return [SlotSet("suggest_booking", False)]  # noqa: FBT003


@utils.handle_action_exceptions
class CheckIsReservable(Action):
    """Action that checks if a place is reservable."""

    def name(self) -> str:
        return "action_check_is_reservable"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        search_history = utils.get_slot(tracker, "search_history", [])
        selected_search = utils.get_slot(tracker, "selected_searches", [])[0]
        selected_result: int = utils.get_slot(tracker, "selected_results", [])[0]

        store = utils.get_kv_store()
        search = store.get_search(search_history[selected_search])
        results = search.results or []
        place = results[selected_result]

        return [SlotSet("is_reservable", place.reservable is True)]


@utils.handle_action_exceptions
class StateNotReservable(Action):
    """Action that informs the user that a place is not reservable."""

    def name(self) -> str:
        return "action_state_not_reservable"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        search_history = utils.get_slot(tracker, "search_history", [])
        selected_search = utils.get_slot(tracker, "selected_searches", [])[0]
        selected_result: int = utils.get_slot(tracker, "selected_results", [])[0]

        store = utils.get_kv_store()
        search = store.get_search(search_history[selected_search])
        results = search.results or []
        place = results[selected_result]

        dispatcher.utter_message(
            response="utter_place_not_reservable",
            place_name=place.display_name.text,  # type: ignore
        )

        return []


@utils.handle_action_exceptions
class StartBooking(Action):
    """Action that starts the booking process."""

    def name(self) -> str:
        return "action_start_booking"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        store = utils.get_kv_store()
        history = utils.get_slot(tracker, "booking_history", [])

        intents = utils.get_last_intents(tracker)
        if "inform_booking" in intents:
            # the user is modifying an existing booking
            idx = utils.get_slot(tracker, "selected_bookings", [])[0]
            booking = store.get_booking(history[idx])

            return [
                SlotSet("booking_place", utils.serialize(booking.parameters.place)),
                SlotSet("booking_datetime", booking.parameters.date.isoformat()),
                SlotSet("booking_datetime_error", None),
                SlotSet("booking_people_count", booking.parameters.num_people),
                SlotSet("booking_people_count_error", None),
                SlotSet("booking_author", booking.parameters.author),
            ]

        # the user is creating a new booking
        history = history.copy()
        history.append(None)

        search_history = utils.get_slot(tracker, "search_history", [])
        selected_search = utils.get_slot(tracker, "selected_searches", [])[0]
        selected_result: int = utils.get_slot(tracker, "selected_results", [])[0]
        search = store.get_search(search_history[selected_search])
        if search.results is None:
            msg = "Cannot start booking without search results"
            raise RuntimeError(msg)
        result = search.results[selected_result]

        dispatcher.utter_message(
            response="utter_start_booking",
            place_name=result.display_name.text,  # type: ignore
        )

        return [
            SlotSet("booking_history", history),
            SlotSet("selected_bookings", [len(history) - 1]),
            SlotSet("booking_place", utils.serialize(result)),
            SlotSet("booking_datetime", None),
            SlotSet("booking_datetime_error", None),
            SlotSet("booking_people_count", None),
            SlotSet("booking_people_count_error", None),
            SlotSet("booking_author", None),
        ]


@utils.handle_action_exceptions
class ConfirmBooking(Action):
    """Action to ask for confirmation of a booking."""

    def name(self) -> str:
        return "action_confirm_booking"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        date = utils.get_slot(tracker, "booking_datetime")
        date = datetime.fromisoformat(date)
        count = utils.get_slot(tracker, "booking_people_count")
        author = utils.get_slot(tracker, "booking_author")

        history = utils.get_slot(tracker, "booking_history", [])
        idx = utils.get_slot(tracker, "selected_bookings", [])[0]

        if history[idx] is None:
            dispatcher.utter_message(
                response="utter_confirm_booking",
                datetime=date.strftime("%A, %B %d, %Y at %I:%M %p"),
                people_count=count,
                author=author,
            )
        else:
            booking = utils.get_kv_store().get_booking(history[idx])
            msg = "Do you confirm the following changes to your booking?\n"
            if booking.parameters.num_people != count:
                msg += f"- number of people: {count}\n"
            if booking.parameters.date != date:
                msg += (
                    f"- date and time: {date.strftime('%A, %B %d, %Y at %I:%M %p')}\n"
                )
            if booking.parameters.author != author:
                msg += f"- made by: {author}\n"

            dispatcher.utter_message(text=msg)

        return []


@utils.handle_action_exceptions
class CreateBooking(Action):
    """Action that creates a booking."""

    def name(self) -> str:
        return "action_create_booking"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "booking_history", [])
        idx = utils.get_slot(tracker, "selected_bookings", [])[0]

        place = utils.get_slot(tracker, "booking_place")
        place = utils.deserialize(places.Place, place)
        date = datetime.fromisoformat(utils.get_slot(tracker, "booking_datetime"))
        count = utils.get_slot(tracker, "booking_people_count")
        author = utils.get_slot(tracker, "booking_author")

        parameters = BookingParameters(place, date, count, author)
        booking = BookingData(parameters)
        store = utils.get_kv_store()

        if history[idx] is not None:
            # the user was modifying an existing booking
            dispatcher.utter_message(response="utter_booking_modified")
            store.update_booking(history[idx], booking)
            return []

        # the user was creating a new booking
        dispatcher.utter_message(response="utter_booking_created")
        history = history.copy()
        history[idx] = store.add_booking(booking)

        return [
            SlotSet("booking_history", history),
            SlotSet("selected_bookings", [idx]),
        ]


@utils.handle_action_exceptions
class CancelBooking(Action):
    """Action that cancels the booking currently in progress."""

    def name(self) -> str:
        return "action_cancel_booking"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "booking_history", [])
        idx = utils.get_slot(tracker, "selected_bookings", [])[0]

        if history[idx] is None:
            # the user was creating the booking, so we just remove it
            dispatcher.utter_message(response="utter_cancel_booking")
            history = history.copy()
            history.pop(idx)
            return [
                SlotSet("booking_history", history),
                SlotSet("selected_bookings", []),
            ]

        # the user was modifying an existing booking, so we make no changes
        dispatcher.utter_message(response="utter_cancel_modify_booking")
        return []


@utils.handle_action_exceptions
class CheckFutureBooking(Action):
    """Action that checks if a booking is in the future."""

    def name(self) -> str:
        return "action_check_future_booking"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "booking_history", [])
        idx = utils.get_slot(tracker, "selected_bookings", [])[0]
        if history[idx] is None:
            return [SlotSet("is_future_booking", True)]  # noqa: FBT003

        store = utils.get_kv_store()
        booking = store.get_booking(history[idx])

        # as of now, we do not deal with timezones
        # we assume the user is in the same timezone as the chatbot
        return [SlotSet("is_future_booking", booking.parameters.date > datetime.now())]  # noqa: DTZ005


# --------------------------------------------------------------------------- #
# Booking details Actions
# --------------------------------------------------------------------------- #


@utils.handle_action_exceptions
class ShowBookingDetails(Action):
    """Action that shows the details of a booking."""

    def name(self) -> str:
        return "action_show_booking_details"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "booking_history", [])
        idx = utils.get_slot(tracker, "selected_bookings", [])[0]

        store = utils.get_kv_store()
        booking = store.get_booking(history[idx])

        date = booking.parameters.date.strftime("%A, %B %d, %Y at %I:%M %p")

        msg = "Here are the details of your booking:\n"
        msg += f"- place: {booking.parameters.place.short_formatted_address}\n"
        msg += f"- date and time: {date}\n"
        msg += f"- number of people: {booking.parameters.num_people}\n"
        msg += f"- made by: {booking.parameters.author}\n"

        dispatcher.utter_message(text=msg)
        return []
