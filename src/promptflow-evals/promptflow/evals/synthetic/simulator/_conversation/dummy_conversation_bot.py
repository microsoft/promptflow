# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
from typing import Dict, List, Optional, Tuple

import jinja2

from .constants import ConversationRole
from .conversation_turn import ConversationTurn


class DummyConversationBot:
    def __init__(
        self,
        role: ConversationRole,
        conversation_template: str,
        instantiation_parameters: Dict[str, str],
    ):
        """
        Create a ConversationBot with specific name, persona and a sentence that can be used as a conversation starter.

        Parameters
        ----------
        role: The role of the bot in the conversation, either USER or ASSISTANT
        model: The LLM model to use for generating responses
        conversation_template: A jinja2 template that describes the conversation,
        this is used to generate the prompt for the LLM
        instantiation_parameters: A dictionary of parameters that are used to instantiate the conversation template
            Dedicated parameters:
                - conversation_starter: A sentence that can be used as a conversation starter, if not provided,
                    the first turn will be generated using the LLM
        """
        # if role == ConversationRole.USER and type(model) == LLAMAChatCompletionsModel:
        #    self.logger.info("We suggest using LLaMa chat model to simulate assistant not to simulate user")

        self.role = role
        self.conversation_template: jinja2.Template = jinja2.Template(
            conversation_template, undefined=jinja2.StrictUndefined
        )
        self.persona_template_args = instantiation_parameters
        if self.role == ConversationRole.USER:
            self.name = self.persona_template_args.get("name", role.value)
        else:
            self.name = self.persona_template_args.get("chatbot_name", role.value) or "Dummy"  # model.name
        # self.model = model

        self.logger = logging.getLogger(repr(self))

        if role == ConversationRole.USER:
            self.conversation_starter: Optional[str] = None
            if "conversation_starter" in self.persona_template_args:
                self.logger.info(
                    "This simulated bot will use the provided conversation starter "
                    '"%s"'
                    "instead of generating a turn using a LLM",
                    repr(self.persona_template_args["conversation_starter"])[:400],
                )
                self.conversation_starter = self.persona_template_args["conversation_starter"]
            else:
                self.logger.info(
                    "This simulated bot will generate the first turn as no conversation starter is provided"
                )

        self.userMessages = [
            "Find the temperature in seattle and add it to the doc",
            "what is the weight of an airplane",
            "how may grams are there in a ton",
            "what is the height of eiffel tower",
            "where do you come from",
            "what is the current time",
        ]

    async def generate_response(
        self,
        conversation_history: List[ConversationTurn],
        max_history: int,
        turn_number: int = 0,
    ) -> Tuple[dict, dict, int, dict]:
        """
        Prompt the ConversationBot for a response.

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
        if turn_number == 0 and self.conversation_starter is not None and self.conversation_starter != "":
            self.logger.info("Returning conversation starter: %s", self.conversation_starter)
            time_taken = 0

            samples = [self.conversation_starter]
            finish_reason = ["stop"]

            parsed_response = {"samples": samples, "finish_reason": finish_reason, "id": None}
            full_response = parsed_response
            return parsed_response, {}, time_taken, full_response

        prompt = self.conversation_template.render(
            conversation_turns=conversation_history[-max_history:], role=self.role.value, **self.persona_template_args
        )

        messages = [{"role": "system", "content": prompt}]

        # The ChatAPI must respond as ASSISTANT, so if this bot is USER, we need to reverse the messages
        if self.role == ConversationRole.USER:  # and (isinstance(self.model, OpenAIChatCompletionsModel) or
            # isinstance(self.model, LLAMAChatCompletionsModel)):
            # in here we need to simulate the user,
            # The chatapi only generate turn as assistant and can't generate turn as user
            # thus we reverse all rules in history messages,
            # so that messages produced from the other bot passed here as user messages
            messages.extend([turn.to_openai_chat_format(reverse=True) for turn in conversation_history[-max_history:]])
            response_data = {
                "id": "cmpl-uqkvlQyYK7bGYrRHQ0eXlWi8",
                "object": "text_completion",
                "created": 1589478378,
                "model": "text-davinci-003",
                "choices": [{"text": f"{self.userMessages[turn_number]}", "index": 0, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
            }
        else:
            messages.extend([turn.to_openai_chat_format() for turn in conversation_history[-max_history:]])
            response_data = {
                "id": "cmpl-uqkvlQyYK7bGYrRHQ0eXlWi7",
                "object": "text_completion",
                "created": 1589478378,
                "model": "text-davinci-003",
                "choices": [{"text": "This is indeed a test response", "index": 0, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
            }

        # response = await self.model.get_conversation_completion(
        #     messages=messages,
        #     session=session,
        #     role=prompt_role,
        # )

        parsed_response = self._parse_response(response_data)

        request = {"messages": messages}

        return parsed_response, request, 0, response_data

    def _parse_response(self, response_data: dict) -> dict:
        # https://platform.openai.com/docs/api-reference/completions
        samples = []
        finish_reason = []
        for choice in response_data["choices"]:
            if "text" in choice:
                samples.append(choice["text"])
            if "finish_reason" in choice:
                finish_reason.append(choice["finish_reason"])

        return {"samples": samples, "finish_reason": finish_reason, "id": response_data["id"]}

    def __repr__(self):
        return f"Bot(name={self.name}, role={self.role.name}, model=dummy)"
