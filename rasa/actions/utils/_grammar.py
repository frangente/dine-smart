# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

import inflect


def agree_with_number(word: str, count: int) -> str:
    """Agrees a word with a number.

    This function will return the singular or plural form of a word based on the
    count provided. If the count is equal to 1, the singular form will be returned,
    otherwise the plural form will be returned.

    Args:
        word: The word to agree.
        count: The number to agree with.

    Returns:
        The agreed word.

    Raises:
        ValueError: If the count is less than 1.
    """
    if count < 1:
        msg = "The count must be greater than or equal to 1."
        raise ValueError(msg)

    return singularize(word) if count == 1 else pluralize(word)


def singularize(word: str) -> str:
    """Returns the singular form of a word.

    !!! note

        If the word is already singular, the same word will be returned.
    """
    engine = inflect.engine()
    singular = engine.singular_noun(word)  # type: ignore
    if singular is False:
        return word
    return singular


def pluralize(word: str) -> str:
    """Returns the plural form of a word.

    !!! note

        If the word is already plural, the same word will be returned.
    """
    engine = inflect.engine()
    # singular_noun returns False if the word is already singular
    # otherwise it returns the singular form
    singular = engine.singular_noun(word)  # type: ignore
    if singular is False:
        return engine.plural_noun(word)  # type: ignore

    return word


def int_to_ordinal(n: int) -> str:
    """Converts an integer into its ordinal representation."""
    n = int(n)
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]

    return str(n) + suffix


def to_second_singular_person(sentence: str) -> str:
    """Converts a sentence to the second singular person."""
    return sentence.replace("I", "you").replace("am", "are").replace("my", "your")
