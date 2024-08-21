# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

import dataclasses
from typing import Literal

from gcp.maps import places


@dataclasses.dataclass
class SearchParameters:
    """The parameters of a search."""

    location: places.Place
    place_type: str | None = None
    place_name: str | None = None
    open_now: bool | None = None
    meal_type: str | None = None
    cuisine_type: str | None = None
    activity: Literal["eat", "drink"] | None = None
    price_range: Literal["any", "inexpensive", "moderate", "expensive"] | None = None
    quality: Literal["any", "moderate", "excellent"] | None = None
    rank_by: Literal["distance", "relevance"] = "relevance"

    def get_price_levels(self) -> list[places.PriceLevel] | None:
        match self.price_range:
            case "any":
                return None
            case "expensive":
                return [places.PriceLevel.EXPENSIVE, places.PriceLevel.VERY_EXPENSIVE]
            case "moderate":
                return [places.PriceLevel.MODERATE]
            case "inexpensive":
                return [places.PriceLevel.INEXPENSIVE]
            case None:
                return None

    def get_min_rating(self) -> float | None:
        match self.quality:
            case "any":
                return None
            case "excellent":
                return 4.5
            case "moderate":
                return 3.5
            case None:
                return None


@dataclasses.dataclass
class SearchData:
    """A search."""

    parameters: SearchParameters
    results: list[places.Place] | None = None
