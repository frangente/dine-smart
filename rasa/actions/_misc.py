# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

import os
from typing import Any

import google.generativeai as genai
from rasa_sdk import Action, Tracker
from rasa_sdk.events import (
    ActionExecuted,
    Restarted,
    SessionStarted,
    SlotSet,
)
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from rasa.shared.core.constants import (
    ACTION_LISTEN_NAME,
    ACTION_RESTART_NAME,
    ACTION_SESSION_START_NAME,
)

from . import utils


@utils.handle_action_exceptions
class Greet(Action):
    """Custom action to greet the user."""

    def name(self) -> str:
        return "action_greet"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        known_user = utils.get_slot(tracker, "known_user")
        if not known_user:
            dispatcher.utter_message(response="utter_first_greet")
            return [SlotSet("known_user", True)]  # noqa: FBT003

        dispatcher.utter_message(response="utter_greet")
        return []


@utils.handle_action_exceptions
class OutOfScope(Action):
    """Custom action to handle out-of-scope queries."""

    def name(self) -> str:
        return "action_out_of_scope"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
        if api_key is None:
            dispatcher.utter_message(response="utter_out_of_scope")
            return []

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=genai.types.GenerationConfig(
                temperature=1,
                top_p=0.95,
                top_k=64,
                max_output_tokens=1000,
                response_mime_type="text/plain",
            ),
        )

        response = await model.generate_content_async(tracker.latest_message["text"])
        text = " ".join(p.text for p in response.parts).strip()
        dispatcher.utter_message(response="utter_out_of_scope_gemini", content=text)

        return []


@utils.handle_action_exceptions
class SessionStart(Action):
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
        events.extend([
            SlotSet(key, value)
            for key, value in tracker.slots.items()
            if value is not None and key not in exclude
        ])
        events.append(SlotSet("num_internal_errors", 0))
        events.append(SlotSet("user_location", None))
        events.append(ActionExecuted(ACTION_LISTEN_NAME))

        return events


@utils.handle_action_exceptions
class Restart(Action):
    """Custom action to restart the conversation."""

    def name(self) -> str:
        return ACTION_RESTART_NAME

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        # clear the database to avoid it growing indefinitely
        store = utils.get_kv_store()

        search_history = utils.get_slot(tracker, "search_history", [])
        for key in search_history:
            store.delete_search(key)

        booking_history = utils.get_slot(tracker, "booking_history", [])
        for key in booking_history:
            store.delete_booking(key)

        return [Restarted()]
