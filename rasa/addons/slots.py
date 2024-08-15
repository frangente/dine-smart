# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

"""Custom slot types."""

from typing_extensions import override

from rasa.shared.core.slots import Slot


class EmptySingleMultipleList(Slot):
    """Custom slot type for a list that can be empty, contain a single element, or
    multiple elements.
    """  # noqa: D205

    type_name = "empty_single_multiple_list"  # type: ignore

    @override
    def _feature_dimensionality(self) -> int:
        return 3

    @override
    def _as_feature(self) -> list[float]:
        if not self.value:
            return [1.0, 0.0, 0.0]
        if len(self.value) == 1:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]
