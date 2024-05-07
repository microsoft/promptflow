# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# noqa: E402

import copy
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import jinja2

from .._model_tools import LLMBase, OpenAIChatCompletionsModel, RetryClient
from .constants import ConversationRole


@dataclass
class ConversationTurn:
    role: "ConversationRole"
    name: Optional[str] = None
    message: str = ""
    full_response: Optional[Any] = None
    request: Optional[Any] = None

    def to_openai_chat_format(self, reverse: bool = False) -> dict:
        if reverse is False:
            return {"role": self.role.value, "content": self.message}
        if self.role == ConversationRole.ASSISTANT:
            return {"role": ConversationRole.USER.value, "content": self.message}
        return {"role": ConversationRole.ASSISTANT.value, "content": self.message}

    def to_annotation_format(self, turn_number: int) -> dict:
        return {
            "turn_number": turn_number,
            "response": self.message,
            "actor": self.role.value if self.name is None else self.name,
            "request": self.request,
            "full_json_response": self.full_response,
        }

    def __str__(self) -> str:
        return f"({self.role.value}): {self.message}"


class ConversationBot:
    def __init__(
        self,
        *,
        role: ConversationRole,
        model: Union[LLMBase, OpenAIChatCompletionsModel],
        conversation_template: str,
        instantiation_parameters: Dict[str, str],
    ):
        """
        Create a ConversationBot with specific name, persona and a sentence that can be used as a conversation starter.

        :param role: The role of the bot in the conversation, either USER or ASSISTANT.
        :type role: ConversationRole
        :param model: The LLM model to use for generating responses.
        :type model: OpenAIChatCompletionsModel
        :param conversation_template: A Jinja2 template describing the conversation to generate the prompt for the LLM
        :type conversation_template: str
        :param instantiation_parameters: A dictionary of parameters used to instantiate the conversation template
        :type instantiation_parameters: dict
        """

        self.role = role
        self.conversation_template_orig = conversation_template
        self.conversation_template: jinja2.Template = jinja2.Template(
            conversation_template, undefined=jinja2.StrictUndefined
        )
        self.persona_template_args = instantiation_parameters
        if self.role == ConversationRole.USER:
            self.name = self.persona_template_args.get("name", role.value)
        else:
            self.name = self.persona_template_args.get("chatbot_name", role.value) or model.name
        self.model = model

        self.logger = logging.getLogger(repr(self))
        self.conversation_starter = None  # can either be a dictionary or jinja template
        if role == ConversationRole.USER:
            if "conversation_starter" in self.persona_template_args:
                conversation_starter_content = self.persona_template_args["conversation_starter"]
                if isinstance(conversation_starter_content, dict):
                    self.conversation_starter = conversation_starter_content
                else:
                    self.conversation_starter = jinja2.Template(
                        conversation_starter_content, undefined=jinja2.StrictUndefined
                    )
            else:
                self.logger.info(
                    "This simulated bot will generate the first turn as no conversation starter is provided"
                )

    async def generate_response(
        self,
        session: RetryClient,
        conversation_history: List[ConversationTurn],
        max_history: int,
        turn_number: int = 0,
    ) -> Tuple[dict, dict, int, dict]:
        """
        Prompt the ConversationBot for a response.

        :param session: The aiohttp session to use for the request.
        :type session: RetryClient
        :param conversation_history: The turns in the conversation so far.
        :type conversation_history: List[ConversationTurn]
        :param max_history: Parameters used to query GPT-4 model.
        :type max_history: int
        :param turn_number: Parameters used to query GPT-4 model.
        :type turn_number: int
        :return: The response from the ConversationBot.
        :rtype: Tuple[dict, dict, int, dict]
        """

        # check if this is the first turn and the conversation_starter is not None,
        # return the conversations starter rather than generating turn using LLM
        if turn_number == 0 and self.conversation_starter is not None:
            # if conversation_starter is a dictionary, pass it into samples as is
            if isinstance(self.conversation_starter, dict):
                samples = [self.conversation_starter]
            else:
                samples = [self.conversation_starter.render(**self.persona_template_args)]  # type: ignore[attr-defined]
            time_taken = 0

            finish_reason = ["stop"]

            parsed_response = {"samples": samples, "finish_reason": finish_reason, "id": None}
            full_response = parsed_response
            return parsed_response, {}, time_taken, full_response

        try:
            prompt = self.conversation_template.render(
                conversation_turns=conversation_history[-max_history:],
                role=self.role.value,
                **self.persona_template_args,
            )
        except Exception:  # pylint: disable=broad-except
            import code

            code.interact(local=locals())

        messages = [{"role": "system", "content": prompt}]

        # The ChatAPI must respond as ASSISTANT, so if this bot is USER, we need to reverse the messages
        if (self.role == ConversationRole.USER) and (isinstance(self.model, (OpenAIChatCompletionsModel))):
            # in here we need to simulate the user, The chatapi only generate turn as assistant and
            # can't generate turn as user
            # thus we reverse all rules in history messages,
            # so that messages produced from the other bot passed here as user messages
            messages.extend([turn.to_openai_chat_format(reverse=True) for turn in conversation_history[-max_history:]])
            prompt_role = ConversationRole.USER.value
        else:
            messages.extend([turn.to_openai_chat_format() for turn in conversation_history[-max_history:]])
            prompt_role = self.role.value

        response = await self.model.get_conversation_completion(
            messages=messages,
            session=session,
            role=prompt_role,
        )

        return response["response"], response["request"], response["time_taken"], response["full_response"]

    def __repr__(self):
        return f"Bot(name={self.name}, role={self.role.name}, model={self.model.__class__.__name__})"


class CallbackConversationBot(ConversationBot):
    def __init__(self, callback, user_template, user_template_parameters, *args, **kwargs):
        self.callback = callback
        self.user_template = user_template
        self.user_template_parameters = user_template_parameters

        super().__init__(*args, **kwargs)

    async def generate_response(
        self,
        session: "RetryClient",
        conversation_history: List[Any],
        max_history: int,
        turn_number: int = 0,
    ) -> Tuple[dict, dict, int, dict]:
        chat_protocol_message = self._to_chat_protocol(
            self.user_template, conversation_history, self.user_template_parameters
        )
        msg_copy = copy.deepcopy(chat_protocol_message)
        result = {}
        start_time = time.time()
        result = await self.callback(msg_copy)
        end_time = time.time()
        if not result:
            result = {
                "messages": [{"content": "Callback did not return a response.", "role": "assistant"}],
                "finish_reason": ["stop"],
                "id": None,
                "template_parameters": {},
            }
        self.logger.info("Using user provided callback returning response.")

        time_taken = end_time - start_time
        try:
            response = {
                "samples": [result["messages"][-1]["content"]],
                "finish_reason": ["stop"],
                "id": None,
            }
        except Exception as exc:
            raise TypeError("User provided callback do not conform to chat protocol standard.") from exc

        self.logger.info("Parsed callback response")

        return response, {}, time_taken, result

    def _to_chat_protocol(self, template, conversation_history, template_parameters):
        messages = []

        for _, m in enumerate(conversation_history):
            messages.append({"content": m.message, "role": m.role.value})

        return {
            "template_parameters": template_parameters,
            "messages": messages,
            "$schema": "http://azureml/sdk-2-0/ChatConversation.json",
        }


__all__ = [
    "ConversationRole",
    "ConversationBot",
    "CallbackConversationBot",
    "ConversationTurn",
]
