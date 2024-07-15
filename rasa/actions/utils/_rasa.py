# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

"""Utilities for Rasa."""

import logging
from typing import Any, Literal, TypedDict, overload

from rasa_sdk import Action, Tracker
from rasa_sdk.events import ActionExecuted, Restarted, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from typing_extensions import NotRequired

from rasa.shared.core.constants import ACTION_BACK_NAME, ACTION_DEACTIVATE_LOOP_NAME
from rasa.shared.nlu.constants import (
    ENTITIES,
    ENTITY_ATTRIBUTE_GROUP,
    ENTITY_ATTRIBUTE_ROLE,
    ENTITY_ATTRIBUTE_TYPE,
    ENTITY_ATTRIBUTE_VALUE,
    INTENT,
    INTENT_NAME_KEY,
)

_logger = logging.getLogger(__name__)


def handle_action_exceptions(x: type[Action]) -> type[Action]:
    """Wraps the `Action.run` method to handle exceptions."""

    async def run(
        self: Action,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[dict[str, Any]]:
        try:
            return await self.wrapped_run(dispatcher, tracker, domain)  # type: ignore
        except Exception:
            _logger.exception("An unexpected error occurred inside %s", self.name())

            num_errors = get_slot(tracker, "num_internal_errors", 0) + 1

            if num_errors < 3:
                active_loop = tracker.active_loop
                events = [SlotSet("num_internal_errors", num_errors)]
                if not active_loop:
                    events.append(ActionExecuted(ACTION_BACK_NAME))
                else:
                    events.append(ActionExecuted(ACTION_DEACTIVATE_LOOP_NAME))
            else:
                dispatcher.utter_message(response="utter_internal_error_max")
                events = [Restarted()]

            return events

    x.wrapped_run = x.run  # type: ignore
    x.run = run
    return x


@overload
def get_slot(tracker: Tracker, slot_name: str, default: Any) -> Any: ...


@overload
def get_slot(tracker: Tracker, slot_name: str) -> Any: ...


def get_slot(
    tracker: Tracker,
    slot_name: str,
    default: Any | None = None,
) -> Any | None:
    """Gets the value of a slot.

    Args:
        tracker: The tracker.
        slot_name: The name of the slot.
        default: The default value to return if the slot is not set.

    Returns:
        The value of the slot or the default value if the slot is not set.
    """
    slot = tracker.slots.get(slot_name)
    return slot if slot is not None else default


def get_entities(
    tracker: Tracker,
    type_: str,
    role: str | None = None,
    group: str | None = None,
) -> list[dict[str, Any]]:
    """Gets the entities of a certain type, role, or group.

    Args:
        tracker: The tracker.
        type_: The type of the entity.
        role: The role of the entity. If you don't want to filter by role, pass `None`.
            If you want to select entities without a role, pass an empty string.
        group: The group of the entity. If you don't want to filter by group, pass
            `None`. If you want to select entities without a group, pass an empty
            string.

    Returns:
        The entities that match the given type, role, and group.
    """
    entities = []
    for entity in tracker.latest_message.get(ENTITIES, []):
        if entity.get(ENTITY_ATTRIBUTE_TYPE) == type_:
            if role and entity.get(ENTITY_ATTRIBUTE_ROLE, "") != role:
                continue
            if group and entity.get(ENTITY_ATTRIBUTE_GROUP, "") != group:
                continue
            entities.append(entity)

    return entities


def get_entity_values(
    tracker: Tracker,
    type_: str,
    role: str | None = None,
    group: str | None = None,
) -> list[str]:
    """Gets the values of the entities of a certain type, role, or entity.

    Args:
        tracker: The tracker.
        type_: The type of the entity.
        role: The role of the entity. If you don't want to filter by role, pass `None`.
            If you want to select entities without a role, pass an empty string.
        group: The group of the entity. If you don't want to filter by group, pass
            `None`. If you want to select entities without a group, pass an empty
            string.

    Returns:
        The values of the entities that match the given type, role, and group.
    """
    return [
        entity[ENTITY_ATTRIBUTE_VALUE]
        for entity in get_entities(tracker, type_, role, group)
    ]


def get_intents(tracker: Tracker) -> list[str]:
    """Gets the intents of the latest message.

    Args:
        tracker: The tracker.

    Returns:
        The intents of the latest message.
    """
    intent = tracker.latest_message.get(INTENT)
    if not intent:
        return []

    return intent[INTENT_NAME_KEY].split("+")


def count_action_inside_form(tracker: Tracker, action_name: str) -> int:
    """Counts how many times an action was executed inside the current form.

    Args:
        tracker: The tracker.
        action_name: The name of the action.

    Returns:
        The number of times the action was executed inside the current form.

    Raises:
        RuntimeError: If no form is active.
    """
    active_loop = tracker.active_loop
    if not active_loop:
        msg = "No form is active."
        raise RuntimeError(msg)

    count = 0
    for event in reversed(tracker.events):
        if event.get("event") == "action":
            if event.get("name") == active_loop["name"]:
                break

            if event.get("name") == action_name:
                count += 1

    return count


class Search(TypedDict):
    title: NotRequired[str]
    title_given_by_user: NotRequired[bool]
    rank_by: NotRequired[Literal["relevance", "distance"]]
    open_now: NotRequired[bool]
    location: NotRequired[dict[str, Any]]
    place_name: NotRequired[str]
    place_type: NotRequired[str]
    primary_type: NotRequired[str]
    cuisine_type: NotRequired[str]
    price_range: NotRequired[str]
    quality: NotRequired[str]
    next_page_token: NotRequired[str]
    results: NotRequired[list[dict[str, Any]]]


def get_current_search(tracker: Tracker) -> Search:
    """Returns the current search from the search history."""
    selected_searches = tracker.slots["selected_searches"]
    search_history = tracker.slots.get("search_history", [])
    return search_history[selected_searches[0]]
