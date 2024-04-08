# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
import time
from typing import Dict, List, Tuple

from promptflow.evals.synthetic.simulator._model_tools import RetryClient

from .augloop_client import AugLoopClient, AugLoopParams
from .constants import ConversationRole
from .conversation_bot import ConversationBot
from .conversation_turn import ConversationTurn


class AugLoopConversationBot(ConversationBot):
    def __init__(  # pylint: disable=super-init-not-called
        self,
        role: ConversationRole,
        augLoopParams: AugLoopParams,
        instantiation_parameters: Dict[str, str],
    ):
        """
        Create an AugLoop ConversationBot with specific name,
        persona and a sentence that can be used as a conversation starter.

        Parameters
        ----------
        role: The role of the bot in the conversation, either USER or ASSISTANT
        augLoopParams: The augloop params to use for connecting to augloop
        conversation_template: A jinja2 template that describes the conversation,
        this is used to generate the prompt for the LLM
        instantiation_parameters: A dictionary of parameters that are used to instantiate the conversation template
        """
        if role == ConversationRole.USER:
            raise Exception("AugLoop conversation Bot is not enabled for USER role")

        self.role = role
        self.augLoopParams = augLoopParams

        self.persona_template_args = instantiation_parameters
        self.name = (
            self.persona_template_args.get("chatbot_name", role.value) or f"Augloop_{augLoopParams.workflowName}"
        )

        self.logger = logging.getLogger(repr(self))

        self.augLoopClient = AugLoopClient(augLoopParams)

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

        messageToSend = conversation_history[-1].message

        time_start = time.time()

        # send message
        response_data = self.augLoopClient.send_signal_and_wait_for_annotation(messageToSend)

        time_taken = time.time() - time_start

        if not response_data["success"]:
            raise Exception("Unexpected result from Augloop")

        parsed_response = {
            "samples": response_data["messages"],
            "id": response_data["id"],
        }

        messages = [{"role": "system", "content": messageToSend}]
        request = {"messages": messages}

        return parsed_response, request, int(time_taken), response_data["full_message"]

    def __repr__(self):
        return f"Bot(name={self.name}, role={self.role.name}, model=Augloop)"
