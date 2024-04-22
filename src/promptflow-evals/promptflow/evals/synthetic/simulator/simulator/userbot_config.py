# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
from typing import Dict, Optional

from promptflow.evals.synthetic.simulator._model_tools.models import OpenAIChatCompletionsModel
from promptflow.evals.synthetic.simulator.simulator._token_manager import PlainTokenManager

logger = logging.getLogger(__name__)


class UserBotConfig:
    """
    A class to represent the configuration for a UserBot representing the user in a non-adversarial simulator.
    """

    def __init__(
        self, *, api_key: str, api_base: str, model_name: str, api_version: str, model_kwargs: Optional[Dict] = None
    ):
        """
        Constructs all the necessary attributes for the UserBotConfig object.

        :keyword api_key: The API key for the bot.
        :paramtype api_key: str

        :keyword api_base: The base URL for the API.
        :paramtype api_base: str

        :keyword model_name: The name of the model to use.
        :paramtype model_name: str

        :keyword api_version: The version of the API to use.
        :paramtype api_version: str

        :keyword model_kwargs: Additional keyword arguments for the model.
        :paramtype model_kwargs: Optional[Dict]
        """

        self.api_key = api_key
        self.api_base = api_base
        self.model_name = model_name
        self.api_version = api_version
        self.model_kwargs = model_kwargs if model_kwargs is not None else {}

    def to_open_ai_chat_completions(self) -> OpenAIChatCompletionsModel:
        """
        Returns an instance of OpenAIChatCompletionsModel configured with the bot's settings.

        :return: An instance of OpenAIChatCompletionsModel configured with the bot's settings.
        :rtype: OpenAIChatCompletionsModel
        """
        token_manager = PlainTokenManager(
            openapi_key=self.api_key,
            auth_header="api-key",
            logger=logging.getLogger("bot_token_manager"),
        )
        return OpenAIChatCompletionsModel(
            endpoint_url=f"{self.api_base}openai/deployments/{self.model_name}/chat/completions",
            token_manager=token_manager,
            api_version=self.api_version,
            name=self.model_name,
            **self.model_kwargs,
        )
