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
        webhook = Blueprint("alexa_webhook", __name__)

        @webhook.route("/", methods=["GET"])
        async def health(_request: Request) -> HTTPResponse:  # type: ignore
            return response.json({"status": "ok"})

        @webhook.route("/webhook", methods=["POST"])
        async def receive(request: Request) -> HTTPResponse:  # type: ignore
            message, end_session = await _handle_request(request, on_new_message)

            # convert the message to SSML
            parts = message.split("\n")
            msg = "<speak>"
            for idx, part in enumerate(parts):
                if part.startswith("-"):
                    # if it starts with a number followed by a dot
                    # add a pause before the text
                    if idx == 0:
                        msg += "<p>"
                    else:
                        msg += "<break time='500ms'/>"
                    msg += f"<s>{part}</s>"
                elif part[0].isnumeric():
                    if idx > 0:
                        msg += "<break time='500ms'/>"

                    number, text = part.split(".", 1)
                    msg += f"<s>{number}.<break time='500ms'/>{text}</s>"
                else:
                    if idx > 0:
                        msg += "</p>"

                    msg += f"<p><s>{part}</s>"
            msg += "</p></speak>"

            escapes = "".join([chr(char) for char in range(1, 32)])
            translator = str.maketrans("", "", escapes)
            msg = msg.translate(translator)
            msg = msg.replace("&", "and")

            r = {
                "version": "1.0",
                "sessionAttributes": {"status": "test"},
                "response": {
                    "outputSpeech": {
                        "type": "SSML",
                        "ssml": msg,
                        "playBehavior": "REPLACE_ENQUEUED",
                    },
                    "reprompt": {
                        "outputSpeech": {
                            "type": "SSML",
                            "ssml": msg,
                            "playBehavior": "REPLACE_ENQUEUED",
                        }
                    },
                    "shouldEndSession": end_session,
                },
            }
            return response.json(r)

        return webhook


async def _handle_request(  # noqa: C901, PLR0912
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
    if not locale.startswith("en"):
        message = "Sorry, this skill only supports English."
        end_session = True
        return message, end_session

    user_id = payload["session"]["user"]["userId"]

    match payload["request"]["type"]:
        case "CanFulfillIntentRequest":
            # Alexa is asking if the skill can fulfill the intent
            # we don't support this yet
            raise NotImplementedError
        case "LaunchRequest":
            # if the user is starting the skill, create a fake
            # intent to trigger the welcome message
            text = "hi"
            end_session = False
        case "IntentRequest":
            intent = payload["request"]["intent"]["name"]
            match intent:
                case "AMAZON.StopIntent":
                    text = "goodbye"
                    end_session = True
                case "AMAZON.HelpIntent":
                    text = "help"
                    end_session = False
                case "AMAZON.CancelIntent":
                    text = "cancel"
                    end_session = False
                case "ReturnUserInput":
                    text = payload["request"]["intent"]["slots"]["text"]["value"]
                    end_session = False
                case _:
                    message = "Could you please repeat that?"
                    end_session = False
                    return message, end_session
        case "SessionEndedRequest":
            # if the user is ending the skill, create a fake
            # intent to let Rasa know the user is leaving
            text = "goodbye"
            end_session = True
        case _:
            msg = f"Unsupported request type '{payload['request']['type']}'."
            raise RuntimeError(msg)

    out = CollectingOutputChannel()

    metadata = {"locale": locale}

    # send the user message to Rasa &
    # wait for the response
    await on_new_message(
        UserMessage(
            text=text,
            output_channel=out,
            sender_id=user_id,
            metadata=metadata,
        )
    )
    # extract the text from Rasa's response
    responses = [m["text"] for m in out.messages]
    if len(responses) > 0:
        message = "\n".join(responses)
    else:
        message = "Sorry, can you repeat that please?"
        _logger.error("No response returned from the Rasa server.")

    return message, end_session
