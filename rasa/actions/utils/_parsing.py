# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

import dataclasses
import datetime
from typing import Literal, TypeAlias

import aiohttp
from dateutil import parser

DUCKLING_URL = "http://localhost:8000/parse"


@dataclasses.dataclass(frozen=True)
class Instant:
    value: datetime.datetime
    grain: Literal["second", "minute", "hour", "day", "week", "month", "year"]


@dataclasses.dataclass(frozen=True)
class Interval:
    start: Instant
    end: Instant | None


Time: TypeAlias = Instant | Interval


async def parse_numbers(text: str, locale: str = "en_US") -> list[int]:
    """Parses numbers from a given text using Duckling."""
    async with aiohttp.ClientSession() as session:
        data = {"text": text, "locale": locale, "dims": ["number"]}
        async with session.post(DUCKLING_URL, data=data) as response:
            response.raise_for_status()

            entities = await response.json()
            return [e["value"]["value"] for e in entities if e["dim"] == "number"]


async def parse_ordinals(text: str, locale: str = "en_US") -> list[int]:
    """Parses ordinals from a given text using Duckling."""
    async with aiohttp.ClientSession() as session:
        data = {"text": text, "locale": locale, "dims": ["ordinal"]}
        async with session.post(DUCKLING_URL, data=data) as response:
            response.raise_for_status()

            entities = await response.json()
            return [e["value"]["value"] for e in entities if e["dim"] == "ordinal"]


async def parse_times(text: str, locale: str = "en_US") -> list[Time]:
    """Parses times from a given text using Duckling."""
    async with aiohttp.ClientSession() as session:
        data = {"text": text, "locale": locale, "dims": ["time"]}
        async with session.post(DUCKLING_URL, data=data) as response:
            response.raise_for_status()

            entities = await response.json()
            times = []
            for ent in entities:
                if ent["dim"] != "time":
                    continue
                ent = ent["value"]  # noqa: PLW2901
                if ent["type"] == "interval":
                    start = Instant(
                        value=parser.parse(ent["from"]["value"]).replace(tzinfo=None),
                        grain=ent["from"]["grain"],
                    )
                    if "to" in ent:
                        end = Instant(
                            value=parser.parse(ent["to"]["value"]).replace(tzinfo=None),
                            grain=ent["to"]["grain"],
                        )
                    else:
                        end = None

                    times.append(Interval(start, end))
                else:
                    times.append(
                        Instant(
                            value=parser.parse(ent["value"]).replace(tzinfo=None),
                            grain=ent["grain"],
                        )
                    )

            return times
