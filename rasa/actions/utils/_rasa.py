# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

"""Utilities for Rasa."""

import logging
from typing import Any, overload

from rasa_sdk import Action, Tracker
from rasa_sdk.events import FollowupAction, Restarted, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from rasa.shared.core.constants import ACTION_BACK_NAME
from rasa.shared.nlu.constants import (
    ENTITIES,
    ENTITY_ATTRIBUTE_GROUP,
    ENTITY_ATTRIBUTE_ROLE,
    ENTITY_ATTRIBUTE_TYPE,
    ENTITY_ATTRIBUTE_VALUE,
    INTENT,
    INTENT_NAME_KEY,
)

from ._grammar import agree_with_number, int_to_ordinal, pluralize, singularize
from ._parsing import parse_numbers, parse_ordinals

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
                events = [SlotSet("num_internal_errors", num_errors)]
                dispatcher.utter_message(response="utter_internal_error")
                events.append(FollowupAction(ACTION_BACK_NAME))
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


_ALL_MENTIONED = [
    "all",
    "every",
    "each",
    "them",
    "everything",
    "these",
    "those",
    "their",
    "theirs",
    "they",
    "themself",
    "themselves",
    "everyone",
    "everybody",
    "everything",
]


async def resolve_mentions(  # noqa: C901, PLR0912, PLR0915
    tracker: Tracker,
    selected: list[int],
    num_entities: int,
    entity_type: str | list[str],
    default_number: int = 5,
) -> tuple[list[int], list[str]]:
    text = tracker.latest_message.get("text", "").lower()
    match entity_type:
        case str():
            entity_type = singularize(entity_type).lower()
            entity_type_plural = pluralize(entity_type).lower()
            relative = entity_type not in text
            if entity_type_plural not in text:
                default_number = 1
        case list():
            entity_type = [singularize(e).lower() for e in entity_type]
            entity_type_plural = [pluralize(e).lower() for e in entity_type]
            relative = all(e not in text for e in entity_type)
            if all(e not in text for e in entity_type_plural):
                default_number = 1

            entity_type = entity_type[0]
            entity_type_plural = entity_type_plural[0]

    candidates = []
    errors = []
    for mention in get_entity_values(tracker, "mention"):
        if any(word in mention for word in _ALL_MENTIONED):
            if selected:
                candidates.extend(selected)
            else:
                candidates.extend(range(num_entities))
        elif "current" in mention or "selected" in mention:
            if selected:
                candidates.extend(selected)
            else:
                msg = f"you haven't selected any {entity_type} yet"
                errors.append(msg)
        elif "oldest" in mention or "first" in mention:
            number = await parse_numbers(mention)
            number = number[0] if number else (min(default_number, num_entities))
            if relative and number <= len(selected):
                candidates.extend(selected[:number])
            elif number <= num_entities:
                candidates.extend(range(number))
            else:
                msg = (
                    f"there are only {num_entities} {entity_type_plural}, so I can't "
                    f"select the first {number}"
                )
                errors.append(msg)
        elif "last" in mention or "latest" in mention or "newest" in mention:
            number = await parse_numbers(mention)
            number = number[0] if number else (min(default_number, num_entities))
            if relative and number <= len(selected):
                candidates.extend(selected[-number:])
            elif number <= num_entities:
                candidates.extend(range(num_entities - number, num_entities))
            else:
                msg = (
                    f"there are only {num_entities} {entity_type_plural}, so I can't "
                    f"select the last {number}"
                )
                errors.append(msg)
        elif "next" in mention:
            current = max(selected)
            number = await parse_numbers(mention)
            number = (
                number[0] if number else min(default_number, num_entities - current)
            )
            if len(selected) == 0:
                msg = (
                    f"you haven't selected any {entity_type} yet, so I can't "
                    f"select the next {number}"
                )
                errors.append(msg)
            elif current + number < num_entities:
                candidates.extend(range(current + 1, current + number + 1))
            else:
                msg = (
                    f"there are no more {entity_type_plural}, so I can't "
                    f"select the next {number}"
                )
                errors.append(msg)
        elif "previous" in mention:
            current = min(selected)
            number = await parse_numbers(mention)
            number = number[0] if number else min(default_number, current)
            if len(selected) == 0:
                msg = (
                    f"you haven't selected any {entity_type} yet, so I can't "
                    f"select the previous {number}"
                )
                errors.append(msg)
            elif current - number >= 0:
                candidates.extend(range(current - number, current))
            else:
                msg = (
                    f"there are no previous {entity_type_plural}, so I can't "
                    f"select the previous {number}"
                )
                errors.append(msg)
        else:
            ordinal = await parse_ordinals(mention)
            number = await parse_numbers(mention)
            if not ordinal and not number:
                continue

            if not ordinal:
                number = number[0]
                if number < 1 or number > num_entities:
                    msg = (
                        f"there are only {num_entities} {entity_type_plural}, "
                        f"so I can't select the {int_to_ordinal(number)} one"
                    )
                    errors.append(msg)
                else:
                    candidates.append(number - 1)
            else:
                ordinal = ordinal[0]
                number = number[0] if number else default_number
                start = (ordinal - 1) * number
                end = start + number
                if relative and end < len(selected):
                    candidates.extend(selected[start:end])
                elif end < num_entities:
                    candidates.extend(range(start, end))
                else:
                    msg = (
                        f"there are only {num_entities} {entity_type_plural}, "
                        f"so I can't select the {int_to_ordinal(ordinal)} "
                        f"{agree_with_number('one', end - start)}"
                    )
                    errors.append(msg)

    candidates = sorted(set(candidates))
    return candidates, errors
