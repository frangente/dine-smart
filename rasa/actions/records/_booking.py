# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

import dataclasses
from datetime import datetime
from typing import Any

from gcp.maps import places


@dataclasses.dataclass
class BookingParameters:
    """The parameters of a booking."""

    place: places.Place
    date: datetime
    num_people: int
    author: str

    def to_dict(self) -> dict[str, Any]:
        """Returns the parameters as a dictionary."""
        return dataclasses.asdict(self)


@dataclasses.dataclass
class BookingData:
    """A booking."""

    parameters: BookingParameters
