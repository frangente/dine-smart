# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

"""Utility functions for the chatbot."""

from ._grammar import (
    agree_with_number,
    int_to_ordinal,
    pluralize,
    singularize,
    to_second_singular_person,
)
from ._kv_store import KeyValueStore, get_kv_store
from ._misc import (
    deserialize,
    deserialize_iterable,
    join,
    serialize,
    serialize_iterable,
)
from ._parsing import (
    Instant,
    Interval,
    Time,
    parse_numbers,
    parse_ordinals,
    parse_times,
)
from ._rasa import (
    count_action_inside_form,
    get_entities,
    get_entity_values,
    get_last_intents,
    get_slot,
    handle_action_exceptions,
    resolve_mentions,
)
from ._search import (
    find_location,
    find_parkings,
    find_places,
    get_booking_title,
    get_place_title,
    get_search_title,
    is_place_open,
    is_user_location,
    merge_locations,
)

__all__ = [
    # _kv_store
    "KeyValueStore",
    "get_kv_store",
    # _grammar
    "agree_with_number",
    "int_to_ordinal",
    "pluralize",
    "singularize",
    "to_second_singular_person",
    # _misc
    "deserialize",
    "deserialize_iterable",
    "join",
    "serialize",
    "serialize_iterable",
    # _parsing
    "Instant",
    "Interval",
    "Time",
    "parse_numbers",
    "parse_ordinals",
    "parse_times",
    # _rasa
    "count_action_inside_form",
    "get_entities",
    "get_entity_values",
    "get_last_intents",
    "get_slot",
    "handle_action_exceptions",
    "resolve_mentions",
    # _search
    "find_location",
    "find_parkings",
    "find_places",
    "get_booking_title",
    "get_place_title",
    "get_search_title",
    "is_place_open",
    "is_user_location",
    "merge_locations",
]
