# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# pylint: skip-file
import copy
from typing import Any, List, Tuple

from ._conversation import ConversationBot


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
        try:
            result = await self.callback(msg_copy)
        except Exception as exc:
            if "status_code" in dir(exc) and 400 <= exc.status_code < 500 and "response was filtered" in exc.message:
                result = {
                    "messages": [
                        {
                            "content": (
                                "Error: The response was filtered due to the prompt "
                                "triggering Azure OpenAI's content management policy. "
                                "Please modify your prompt and retry."
                            ),
                            "role": "assistant",
                        }
                    ],
                    "finish_reason": ["stop"],
                    "id": None,
                    "template_parameters": {},
                }
        if not result:
            result = {
                "messages": [{"content": "Callback did not return a response.", "role": "assistant"}],
                "finish_reason": ["stop"],
                "id": None,
                "template_parameters": {},
            }

        self.logger.info("Using user provided callback returning response.")

        time_taken = 0
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

        if template_parameters.get("file_content", None) and any(
            "File contents:" not in message["content"] for message in messages
        ):
            messages.append({"content": f"File contents: {template_parameters['file_content']}", "role": "user"})

        return {
            "template_parameters": template_parameters,
            "messages": messages,
            "$schema": "http://azureml/sdk-2-0/ChatConversation.json",
        }
