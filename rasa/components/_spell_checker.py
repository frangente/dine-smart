# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

import logging
import os
from typing import Any

import requests

from rasa.engine.graph import ExecutionContext, GraphComponent
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.nlu.constants import METADATA, TEXT
from rasa.shared.nlu.training_data.message import Message
from rasa.shared.nlu.training_data.training_data import TrainingData

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)


@DefaultV1Recipe.register(
    component_types=DefaultV1Recipe.ComponentType.MESSAGE_FEATURIZER,
    is_trainable=False,
)
class SpellChecker(GraphComponent):
    """Component that checks the spelling of the input message."""

    # ----------------------------------------------------------------------- #
    # Constructor and Factory Methods
    # ----------------------------------------------------------------------- #

    def __init__(self, api_key: str, default_locale: str) -> None:
        super().__init__()

        if default_locale not in _LOCALES:
            msg = (
                f"Unsupported locale '{default_locale}'. "
                f"Supported locales are: {_LOCALES}."
            )
            raise ValueError(msg)

        self._api_key = api_key
        self._locale = default_locale

    @classmethod
    def create(
        cls,
        config: dict[str, Any],
        model_storage: ModelStorage,  # noqa: ARG003
        resource: Resource,  # noqa: ARG003
        execution_context: ExecutionContext,  # noqa: ARG003
    ) -> GraphComponent:
        api_key = os.environ.get(config["api_key_env_var"])
        if api_key is None:
            msg = (
                f"Could not find an API key in the environment variable "
                f"'{config['api_key_env_var']}'."
            )
            raise RuntimeError(msg)
        locale = config["default_locale"]

        return cls(api_key, locale)

    # ----------------------------------------------------------------------- #
    # Public Methods
    # ----------------------------------------------------------------------- #

    @staticmethod
    def required_packages() -> list[str]:
        return ["requests"]

    @staticmethod
    def supported_languages() -> list[str] | None:
        languages = [locale.split("-")[0] for locale in _LOCALES]
        return list(set(languages))

    @staticmethod
    def get_default_config() -> dict[str, Any]:
        return {
            "api_key_env_var": "BING_SEARCH_V7_SUBSCRIPTION_KEY",
            "default_locale": "en-US",
        }

    def process_training_data(self, training_data: TrainingData) -> TrainingData:
        return training_data

    def process(self, messages: list[Message]) -> list[Message]:
        for message in messages:
            medadata = message.get(METADATA) or {}
            locale = medadata.get("locale")
            if locale is not None:
                if locale not in _LOCALES:
                    msg = f"Unsupported locale '{locale}'."
                    raise ValueError(msg)
            else:
                locale = self._locale

            text = message.get(TEXT)
            if text is not None:
                text = _check_spelling(text, self._api_key, locale)
                message.set(TEXT, text)

        return messages


# --------------------------------------------------------------------------- #
# Private API
# --------------------------------------------------------------------------- #


def _check_spelling(text: str, api_key: str, locale: str) -> str:
    endpoint = "https://api.bing.microsoft.com/v7.0/spellcheck"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Ocp-Apim-Subscription-Key": api_key,
    }
    params = {"mode": "proof", "mkt": locale}
    data = {"text": text}

    response = requests.post(
        endpoint,
        headers=headers,
        params=params,
        data=data,
        timeout=5,
    )

    response.raise_for_status()
    body = response.json()

    corrected = text
    for token in body["flaggedTokens"]:
        suggestion = token["suggestions"][0]["suggestion"]
        corrected = corrected.replace(token["token"], suggestion, 1)

    return corrected


_LOCALES = [
    "da-DK",
    "de-AT",
    "de-CH",
    "de-DE",
    "en-AU",
    "en-CA",
    "en-GB",
    "en-ID",
    "en-IN",
    "en-MY",
    "en-NZ",
    "en-PH",
    "en-US",
    "en-ZA",
    "es-AR",
    "es-CL",
    "es-ES",
    "es-MX",
    "es-US",
    "fi-FI",
    "fr-BE",
    "fr-CA",
    "fr-CH",
    "fr-FR",
    "it-IT",
    "ja-JP",
    "ko-KR",
    "nl-BE",
    "nl-NL",
    "no-NO",
    "pl-PL",
    "pt-BR",
    "ru-RU",
    "sv-SE",
    "tr-TR",
    "zh-CN",
    "zh-HK",
    "zh-TW",
]
