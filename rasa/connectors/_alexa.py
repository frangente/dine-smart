# Copyright 2024 Francesco Gentile.
# SPDX-License-Identifier: Apache-2.0

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse

from rasa.core.channels.channel import (
    CollectingOutputChannel,
    InputChannel,
    UserMessage,
)

_logger = logging.getLogger(__name__)


class AlexaConnector(InputChannel):
    """A custom Alexa input channel."""

    @classmethod
    def name(cls) -> str:
        return "alexa"

    def blueprint(
        self,
        on_new_message: Callable[[UserMessage], Awaitable[Any]],
    ) -> Blueprint:
        webhook = Blueprint("alexa_webhook_{}", __name__)

        @webhook.route("/", methods=["GET"])
        async def health(_request: Request) -> HTTPResponse:  # type: ignore
            return response.json({"status": "ok"})

        @webhook.route("/webhook", methods=["POST"])
        async def receive(request: Request) -> HTTPResponse:  # type: ignore
            message, end_session = await _handle_request(request, on_new_message)

            r = {
                "version": "1.0",
                "sessionAttributes": {"status": "test"},
                "response": {
                    "outputSpeech": {
                        "type": "PlainText",
                        "text": message,
                        "playBehavior": "REPLACE_ENQUEUED",
                    },
                    "reprompt": {
                        "outputSpeech": {
                            "type": "PlainText",
                            "text": message,
                            "playBehavior": "REPLACE_ENQUEUED",
                        }
                    },
                    "shouldEndSession": end_session,
                },
            }
            return response.json(r)

        return webhook


async def _handle_request(
    request: Request,
    on_new_message: Callable[[UserMessage], Awaitable[Any]],
) -> tuple[str, bool]:
    payload = request.json
    if payload is None:
        _logger.error("No payload returned from the Alexa server.")

        message = "Could you please repeat that?"
        end_session = False
        return message, end_session

    locale = payload["request"]["locale"]
    intent_type = payload["request"]["type"]
    session_object = payload.get("session", {})
    session_id = session_object.get("sessionId")
    user_id = session_object.get("user", {}).get("userId")
    sender_id = user_id + session_id

    match payload["request"]["type"]:
        case "CanFulfillIntentRequest":
            raise NotImplementedError
        case "LaunchRequest":
            # if the user is starting the skill, create a fake
            # intent to trigger the welcome message
            text = "hi"
        case "IntentRequest":
            text = payload["request"]["intent"]["slots"]["text"]["value"]
        case "SessionEndedRequest":
            # if the user is ending the skill, create a fake
            # intent to let Rasa know the user is leaving
            text = "goodbye"
        case _:
            pass

    # if the user is starting the skill, let them
    # know it worked & what to do next
    if intent_type == "LaunchRequest":
        message = (
            "Hello! Welcome to this Rasa-powered Alexa skill. "
            "You can start by saying 'hi'."
        )
        end_session = False
    else:
        # get the Alexa-detected intent
        intent = payload["request"].get("intent", {}).get("name", "")

        # makes sure the user isn't trying to
        # end the skill
        if intent == "AMAZON.StopIntent":
            end_session = True
            message = "Talk to you later"
        else:
            # get the user-provided text from
            # the slot named "text"
            text = (
                payload["request"]
                .get("intent", {})
                .get("slots", {})
                .get("text", {})
                .get("value", "")
            )

            # initialize output channel
            out = CollectingOutputChannel()

            metadata = {"locale": locale}

            # send the user message to Rasa &
            # wait for the response
            await on_new_message(
                UserMessage(
                    text=text,
                    output_channel=out,
                    sender_id=sender_id,
                    metadata=metadata,
                )
            )
            # extract the text from Rasa's response
            responses = [m["text"] for m in out.messages]
            if len(responses) > 0:
                message = " ".join(responses)
            else:
                message = "Sorry, can you repeat that please?"
                _logger.error("No response returned from the Rasa server.")
            end_session = False

    return message, end_session


# --------------------------------------------------------------------------- #
# Private API
# --------------------------------------------------------------------------- #

_LOCALES = {
    "ar-SA",
    "de-DE",
    "en-AU",
    "en-CA",
    "en-GB",
    "en-IN",
    "en-US",
    "es-ES",
    "es-MX",
    "es-US",
    "fr-CA",
    "fr-FR",
    "hi-IN",
    "it-IT",
    "ja-JP",
    "pt-BR",
}


def _match_locales(locale: str) -> list[str]:
    """Returns the standard locales that match the given locale."""
    if "-" in locale:
        if locale not in _LOCALES:
            msg = f"Unsupported locale '{locale}'."
            raise ValueError(msg)

        return [locale]

    languages = {locale.split("-")[0] for locale in _LOCALES}
    if locale not in languages:
        msg = f"Unsupported locale '{locale}'."
        raise ValueError(msg)

    return [loc for loc in _LOCALES if loc.startswith(locale)]
