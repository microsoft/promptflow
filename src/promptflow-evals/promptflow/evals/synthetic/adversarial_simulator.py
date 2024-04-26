# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
from typing import Any, Callable, Dict

from ._model_tools import (
    CONTENT_HARM_TEMPLATES_COLLECTION_KEY,
    AdversarialTemplateHandler,
    ManagedIdentityAPITokenManager,
    RAIClient,
    TokenScope,
)


class AdversarialSimulator:
    def __init__(self, *, template: str, project_scope: Dict[str, Any]):
        if template not in CONTENT_HARM_TEMPLATES_COLLECTION_KEY:
            raise ValueError(f"Template {template} is not a valid adversarial template.")
        self.template = template
        self.project_scope = project_scope
        self.token_manager = ManagedIdentityAPITokenManager(
            token_scope=TokenScope.DEFAULT_AZURE_MANAGEMENT,
            logger=logging.getLogger("AdversarialSimulator"),
        )
        self.rai_client = RAIClient(project_scope=project_scope, token_manager=self.token_manager)
        self.adversarial_template_handler = AdversarialTemplateHandler(
            project_scope=project_scope, rai_client=self.rai_client
        )

    def __call__(
        self,
        max_conversation_turns: int,
        max_simulation_results: int,
        target: Callable,
        api_call_retry_limit: int,
        api_call_retry_sleep_sec: int,
        api_call_delay_sec: int,
        concurrent_async_task: int,
    ):
        # Simulation logic here
        # For demonstration, returns an empty dict
        return {}
