# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from rasa_sdk import Action, Tracker
from rasa_sdk.events import ActionExecuted, SessionStarted, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from rasa.shared.core.constants import ACTION_LISTEN_NAME, ACTION_SESSION_START_NAME

from . import utils


@utils.handle_action_exceptions
class ActionSessionStart(Action):
    """Custom action to start a session and set slots from tracker."""

    def name(self) -> str:
        return ACTION_SESSION_START_NAME

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        events = [SessionStarted()]

        exclude = {"num_internal_errors", "user_location"}

        slots = [
            SlotSet(key, value)
            for key, value in tracker.slots.items()
            if value is not None and key not in exclude
        ]
        slots += [SlotSet("num_internal_errors", 0), SlotSet("user_location", None)]
        events.extend(slots)

        events.append(ActionExecuted(ACTION_LISTEN_NAME))

        return events


@utils.handle_action_exceptions
class ActionGreet(Action):
    """Custom action to greet the user."""

    def name(self) -> str:
        return "action_greet"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        known_user = utils.get_slot(tracker, "known_user", False)  # noqa: FBT003
        if not known_user:
            dispatcher.utter_message(response="utter_first_greet")
            return [SlotSet("known_user", True)]  # noqa: FBT003

        dispatcher.utter_message(response="utter_greet")
        return []
