# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from rasa_sdk import Action
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker
from rasa_sdk.types import DomainDict

from . import utils
from .records import BookingData

_SELECT_INTENTS = {
    "show_bookings",
    "select_bookings",
    "delete_bookings",
    "select",
    "delete",
}


@utils.handle_action_exceptions
class SetSelectedBookings(Action):
    """Action used to set the selected bookings."""

    def name(self) -> str:
        return "action_set_selected_bookings"

    async def run(  # noqa: PLR0911
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "booking_history", [])
        if len(history) == 0:
            return [
                SlotSet("selected_bookings", None),
                SlotSet("selected_bookings_error", "no_bookings"),
            ]

        mentions = utils.get_entity_values(tracker, "mention")
        if not mentions:
            if len(history) == 1:
                return [
                    SlotSet("selected_bookings", [0]),
                    SlotSet("selected_bookings_error", None),
                ]

            intents = set(utils.get_last_intents(tracker))
            text = tracker.latest_message["text"]
            if "show_bookings" in intents or "history" in text or "activity" in text:
                history = utils.get_slot(tracker, "booking_history", [])
                selected = list(range(len(history)))
                return [
                    SlotSet("selected_bookings", selected),
                    SlotSet("selected_bookings_error", None),
                ]

            return [
                SlotSet("selected_bookings", None),
                SlotSet("selected_bookings_error", "no_selection"),
            ]

        selected, errors = await utils.resolve_mentions(
            tracker,
            selected=utils.get_slot(tracker, "selected_bookings", []),
            entity_type=["booking", "reservation"],
            num_entities=len(history),
        )

        if errors:
            msg = "Sorry, but " + utils.join(errors, sep=", ", last_sep=" and ") + ".\n"
            dispatcher.utter_message(text=msg)
            return [SlotSet("selected_bookings_error", "invalid_selection")]

        entities = utils.get_entity_values(tracker, "datetime")
        datetimes = []
        for entity in entities:
            datetimes.extend(await utils.parse_times(entity))
        if datetimes:
            store = utils.get_kv_store()
            bookings = [store.get_booking(key) for key in history]
            for dt in datetimes:
                selected.extend(_get_bookings(bookings, dt))

            selected = list(set(selected))

        if len(selected) == 0:
            return [
                SlotSet("selected_bookings", None),
                SlotSet("selected_bookings_error", "no_bookings_found"),
            ]

        return [
            SlotSet("selected_bookings", selected),
            SlotSet("selected_bookings_error", None),
        ]


@utils.handle_action_exceptions
class ShowSelectedBookings(Action):
    """Action used to show the selected bookings."""

    def name(self) -> str:
        return "action_show_selected_bookings"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        store = utils.get_kv_store()
        history = utils.get_slot(tracker, "booking_history", [])
        selected = utils.get_slot(tracker, "selected_bookings", [])

        if len(selected) == 1:
            booking = store.get_booking(history[selected[0]])
            title = utils.get_booking_title(booking.parameters)
            msg = f"Here is the selected booking: {title}"
        elif len(selected) == len(history):
            msg = "Here is your booking activity:\n"
            for idx, booking_key in enumerate(history):
                booking = store.get_booking(booking_key)
                msg += f"{idx + 1}. {utils.get_booking_title(booking.parameters)}\n"
        else:
            msg = "Here are the selected bookings:\n"
            for idx in selected:
                booking = store.get_booking(history[idx])
                msg += f"{idx + 1}. {utils.get_booking_title(booking.parameters)}\n"

        dispatcher.utter_message(text=msg)
        return []


@utils.handle_action_exceptions
class DeleteSelectedBookings(Action):
    """Action used to delete the selected bookings."""

    def name(self) -> str:
        return "action_delete_selected_bookings"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        history = utils.get_slot(tracker, "booking_history", [])
        selected = set(utils.get_slot(tracker, "selected_bookings", []))
        history = [book for idx, book in enumerate(history) if idx not in selected]

        dispatcher.utter_message(response="utter_deleted_bookings")

        return [
            SlotSet("booking_history", history),
            SlotSet("selected_bookings", None),
        ]


@utils.handle_action_exceptions
class ConfirmDeleteSelectedBookings(Action):
    """Action used to ask for confirmation before deleting the selected bookings."""

    def name(self) -> str:
        return "action_confirm_delete_selected_bookings"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        store = utils.get_kv_store()
        history = utils.get_slot(tracker, "booking_history", [])
        selected = utils.get_slot(tracker, "selected_bookings", [])

        if len(selected) == 1:
            booking = store.get_booking(history[selected[0]])
            title = utils.get_booking_title(booking.parameters)
            msg = f"Are you sure you want to delete the booking: {title}?"
        elif len(selected) == len(history):
            msg = "Are you sure you want to delete all your bookings?"
        else:
            msg = "Are you sure you want to delete the following bookings?\n"
            for idx in selected:
                booking = store.get_booking(history[idx])
                msg += f"- {utils.get_booking_title(booking.parameters)}\n"

        dispatcher.utter_message(text=msg)
        return []


@utils.handle_action_exceptions
class CountSelectedBookings(Action):
    """Action used to count the selected bookings."""

    def name(self) -> str:
        return "action_count_selected_bookings"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        selected = utils.get_slot(tracker, "selected_bookings", [])
        if len(selected) == 0:
            return [SlotSet("selected_bookings_count", "zero")]

        if len(selected) == 1:
            return [SlotSet("selected_bookings_count", "one")]

        return [SlotSet("selected_bookings_count", "multiple")]


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #


def _get_bookings(bookings: list[BookingData], dt: utils.Time) -> list[int]:  # noqa: C901, PLR0912
    """Gets the bookings that match the given time."""
    selected = []
    match dt:
        case utils.Instant(start, grain):
            for idx, booking in enumerate(bookings):
                match grain:
                    case "year":
                        if booking.parameters.date.year == start.year:
                            selected.append(idx)
                    case "month":
                        if (
                            booking.parameters.date.year == start.year
                            and booking.parameters.date.month == start.month
                        ):
                            selected.append(idx)
                    case "week":
                        if (
                            booking.parameters.date.year == start.year
                            and booking.parameters.date.isocalendar()[1]
                            == start.isocalendar()[1]
                        ):
                            selected.append(idx)
                    case "day":
                        if booking.parameters.date.date() == start.date():
                            selected.append(idx)
                    case "hour" | "minute" | "second":
                        if booking.parameters.date == start:
                            selected.append(idx)
        case utils.Interval(start, end):
            start = start.value
            end = end.value if end else start
            for idx, booking in enumerate(bookings):
                if booking.parameters.date >= start and booking.parameters.date <= end:
                    selected.append(idx)

    return selected
