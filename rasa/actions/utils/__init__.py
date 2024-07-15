# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

"""Utility functions for the chatbot."""

from ._db import KeyValueStore, get_kv_store
from ._grammar import (
    agree_with_number,
    int_to_ordinal,
    pluralize,
    singularize,
    to_second_singular_person,
)
from ._maps import get_maps_client
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
    get_current_search,
    get_entities,
    get_entity_values,
    get_intents,
    get_slot,
    handle_action_exceptions,
)

__all__ = [
    # _db
    "KeyValueStore",
    "get_kv_store",
    # _grammar
    "agree_with_number",
    "int_to_ordinal",
    "pluralize",
    "singularize",
    "to_second_singular_person",
    # _maps
    "get_maps_client",
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
    "get_current_search",
    "get_entities",
    "get_entity_values",
    "get_intents",
    "get_slot",
    "handle_action_exceptions",
]
