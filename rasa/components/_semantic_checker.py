# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import aiohttp
from bs4 import BeautifulSoup
from fake_headers import Headers
from sentence_transformers import SentenceTransformer, util

from rasa.engine.graph import ExecutionContext, GraphComponent
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage

# from rasa.nlu.constants import DENSE_FEATURIZABLE_ATTRIBUTES
from rasa.nlu.extractors.extractor import EntityExtractorMixin
from rasa.shared.nlu.constants import (
    ENTITIES,
    ENTITY_ATTRIBUTE_TYPE,
    ENTITY_ATTRIBUTE_VALUE,
    METADATA,
)
from rasa.shared.nlu.training_data.message import Message


@DefaultV1Recipe.register(
    DefaultV1Recipe.ComponentType.ENTITY_EXTRACTOR,
    is_trainable=False,
)
class SemanticChecker(GraphComponent, EntityExtractorMixin):
    """A component that checks if an entity belongs to a given semantic category."""

    # ----------------------------------------------------------------------- #
    # Constructor and Factory Methods
    # ----------------------------------------------------------------------- #

    def __init__(
        self,
        *,
        default_locale: str,
        model_name: str,
        use_gpu: bool,
        min_cosine_similarity: float,
        entities: list[dict[str, str]],
    ) -> None:
        super().__init__()

        self._country = _extract_country(default_locale)

        self._model = SentenceTransformer(model_name)
        if use_gpu:
            self._model = self._model.to("cuda")

        self._min_cosine_similarity = min_cosine_similarity

        self._entities = {}
        for entity in entities:
            if entity["type"] in self._entities:
                msg = f"Duplicate entity type '{entity['type']}' found."
                raise ValueError(msg)

            self._entities[entity["type"]] = entity["template"]

    @classmethod
    def create(
        cls,
        config: dict[str, Any],
        model_storage: ModelStorage,  # noqa: ARG003
        resource: Resource,  # noqa: ARG003
        execution_context: ExecutionContext,  # noqa: ARG003
    ) -> GraphComponent:
        return cls(
            default_locale=config["default_locale"],
            model_name=config["model_name"],
            use_gpu=config["use_gpu"],
            min_cosine_similarity=config["min_cosine_similarity"],
            entities=config["entities"],
        )

    # ----------------------------------------------------------------------- #
    # Public Methods
    # ----------------------------------------------------------------------- #

    @staticmethod
    def required_packages() -> list[str]:
        return ["aiohttp", "fake_headers", "beautifulsoup4", "sentence_transformers"]

    @staticmethod
    def supported_languages() -> list[str] | None:
        languages = [locale.split("-")[0] for locale in _LOCALES]
        return list(set(languages))

    @staticmethod
    def get_default_config() -> dict[str, Any]:
        return {
            "default_locale": "en",
            "model_name": "all-MiniLM-L6-v2",
            "use_gpu": True,
            "min_cosine_similarity": 0.5,
            "entities": [],
        }

    async def process(self, messages: list[Message]) -> list[Message]:
        for message in messages:
            locale = message.get(METADATA).get("locale")
            country = _extract_country(locale) if locale else self._country
            entities = message.get(ENTITIES, []).copy()
            await self._update_entities(entities, country)
            message.set(ENTITIES, entities, add_to_output=True)

        return messages

    # ----------------------------------------------------------------------- #
    # Private Methods
    # ----------------------------------------------------------------------- #

    async def _update_entities(
        self,
        entities: list[dict[str, Any]],
        country: str | None,
    ) -> None:
        for entity in entities:
            if entity[ENTITY_ATTRIBUTE_TYPE] in self._entities:
                template = self._entities[entity[ENTITY_ATTRIBUTE_TYPE]]
                definitions = await _get_definitions(
                    entity[ENTITY_ATTRIBUTE_VALUE], country
                )

                entity["template"] = template
                entity["definitions"] = definitions
                entity["is_correct"] = await self._check_meaning(template, definitions)

                self.add_processor_name(entity)

    async def _check_meaning(self, template: str, definitions: list[str]) -> bool:
        if len(definitions) == 0:
            return False

        embeds = self._model.encode([template, *definitions], convert_to_tensor=True)
        cosine_scores = util.pytorch_cos_sim(embeds[0], embeds[1:])[0]  # type: ignore
        return cosine_scores.max().item() > self._min_cosine_similarity


# --------------------------------------------------------------------------- #
# Private Functions
# --------------------------------------------------------------------------- #


async def _get_definitions(word: str, country: str | None) -> list[str]:
    """Gets the definitions of a word from the Cambridge Dictionary.

    Args:
        word: The word to get the definitions of.
        country: The country code to use in the URL. If `None`, the defeault URL is
            used.

    Returns:
        A list of definitions of the word.
    """
    word = word.replace(" ", "-")
    if country is not None:
        url = f"https://dictionary.cambridge.org/{country}/dictionary/english/{word}"
    else:
        url = f"https://dictionary.cambridge.org/dictionary/english/{word}"
    headers = Headers(headers=True).generate()

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status != 200:
                # the word is not in the dictionary
                return []

            html = BeautifulSoup(await response.text(), "html.parser")
            divs = html.select(".def.ddef_d.db")
            return [div.get_text().strip(":\n ").replace("\n", " ") for div in divs]


_LOCALES = ["en-GB", "en-US"]


def _extract_country(locale: str) -> str | None:
    if "-" in locale:
        if locale not in _LOCALES:
            msg = f"Unsupported locale '{locale}'."
            raise ValueError(msg)

        country = locale.split("-")[1].lower()
        if country == "gb":
            country = "uk"

        return country

    languages = {loc.split("-")[0] for loc in _LOCALES}
    if locale not in languages:
        msg = f"Unsupported locale '{locale}'."
        raise ValueError(msg)

    return None
