# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# noqa: E501
import functools
import logging
from typing import Any, Callable, Dict

from azure.identity import DefaultAzureCredential

from promptflow._sdk._telemetry import ActivityType, monitor_operation
from promptflow.evals.synthetic.adversarial_scenario import AdversarialScenario

from ._model_tools import AdversarialTemplateHandler, ManagedIdentityAPITokenManager, RAIClient, TokenScope
from .adversarial_simulator import AdversarialSimulator

logger = logging.getLogger(__name__)


def monitor_adversarial_scenario(func) -> Callable:
    """Decorator to monitor adversarial scenario.

    :param func: The function to be decorated.
    :type func: Callable
    :return: The decorated function.
    :rtype: Callable
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        scenario = str(kwargs.get("scenario", None))
        max_conversation_turns = kwargs.get("max_conversation_turns", None)
        max_simulation_results = kwargs.get("max_simulation_results", None)
        decorated_func = monitor_operation(
            activity_name="xpia.adversarial.simulator.call",
            activity_type=ActivityType.PUBLICAPI,
            custom_dimensions={
                "scenario": scenario,
                "max_conversation_turns": max_conversation_turns,
                "max_simulation_results": max_simulation_results,
            },
        )(func)

        return decorated_func(*args, **kwargs)

    return wrapper


class IndirectAttackSimulator:
    """
    Initializes the XPIA (cross domain prompt injected attack) jailbreak adversarial simulator with a project scope.

    :param azure_ai_project: Dictionary defining the scope of the project. It must include the following keys:

        * "subscription_id": Azure subscription ID.
        * "resource_group_name": Name of the Azure resource group.
        * "project_name": Name of the Azure Machine Learning workspace.
    :param credential: The credential for connecting to Azure AI project.
    :type credential: ~azure.core.credentials.TokenCredential
    :type azure_ai_project: Dict[str, Any]
    """

    def __init__(self, *, azure_ai_project: Dict[str, Any], credential=None):
        """Constructor."""
        # check if azure_ai_project has the keys: subscription_id, resource_group_name, project_name, credential
        if not all(key in azure_ai_project for key in ["subscription_id", "resource_group_name", "project_name"]):
            raise ValueError(
                "azure_ai_project must contain keys: subscription_id, resource_group_name and project_name"
            )
        if not all(azure_ai_project[key] for key in ["subscription_id", "resource_group_name", "project_name"]):
            raise ValueError("subscription_id, resource_group_name and project_name must not be None")
        if "credential" not in azure_ai_project and not credential:
            credential = DefaultAzureCredential()
        elif "credential" in azure_ai_project:
            credential = azure_ai_project["credential"]
        self.credential = credential
        self.azure_ai_project = azure_ai_project
        self.token_manager = ManagedIdentityAPITokenManager(
            token_scope=TokenScope.DEFAULT_AZURE_MANAGEMENT,
            logger=logging.getLogger("AdversarialSimulator"),
            credential=credential,
        )
        self.rai_client = RAIClient(azure_ai_project=azure_ai_project, token_manager=self.token_manager)
        self.adversarial_template_handler = AdversarialTemplateHandler(
            azure_ai_project=azure_ai_project, rai_client=self.rai_client
        )

    def _ensure_service_dependencies(self):
        if self.rai_client is None:
            raise ValueError("Simulation options require rai services but ai client is not provided.")

    @monitor_adversarial_scenario
    async def __call__(
        self,
        *,
        scenario: AdversarialScenario,
        target: Callable,
        max_conversation_turns: int = 1,
        max_simulation_results: int = 3,
        api_call_retry_limit: int = 3,
        api_call_retry_sleep_sec: int = 1,
        api_call_delay_sec: int = 0,
        concurrent_async_task: int = 3,
    ):
        """
        Initializes the XPIA (cross domain prompt injected attack) jailbreak adversarial simulator with a project scope.
        This simulator converses with your AI system using prompts injected into the context to interrupt normal
        expected functionality by eliciting manipulated content, intrusion and attempting to gather information outside
        the scope of your AI system.

        :keyword scenario: Enum value specifying the adversarial scenario used for generating inputs.
        :paramtype scenario: promptflow.evals.synthetic.adversarial_scenario.AdversarialScenario
        :keyword target: The target function to simulate adversarial inputs against.
            This function should be asynchronous and accept a dictionary representing the adversarial input.
        :paramtype target: Callable
        :keyword max_conversation_turns: The maximum number of conversation turns to simulate.
            Defaults to 1.
        :paramtype max_conversation_turns: int
        :keyword max_simulation_results: The maximum number of simulation results to return.
            Defaults to 3.
        :paramtype max_simulation_results: int
        :keyword api_call_retry_limit: The maximum number of retries for each API call within the simulation.
            Defaults to 3.
        :paramtype api_call_retry_limit: int
        :keyword api_call_retry_sleep_sec: The sleep duration (in seconds) between retries for API calls.
            Defaults to 1 second.
        :paramtype api_call_retry_sleep_sec: int
        :keyword api_call_delay_sec: The delay (in seconds) before making an API call.
            This can be used to avoid hitting rate limits. Defaults to 0 seconds.
        :paramtype api_call_delay_sec: int
        :keyword concurrent_async_task: The number of asynchronous tasks to run concurrently during the simulation.
            Defaults to 3.
        :paramtype concurrent_async_task: int
        :return: A list of dictionaries, each representing a simulated conversation. Each dictionary contains:

         - 'template_parameters': A dictionary with parameters used in the conversation template,
            including 'conversation_starter'.
         - 'messages': A list of dictionaries, each representing a turn in the conversation.
            Each message dictionary includes 'content' (the message text) and
            'role' (indicating whether the message is from the 'user' or the 'assistant').
         - '**$schema**': A string indicating the schema URL for the conversation format.

         The 'content' for 'assistant' role messages may includes the messages that your callback returned.
        :rtype: List[Dict[str, Any]]

        **Output format**

        .. code-block:: python

            return_value = [
                {
                    'template_parameters': {},
                    'messages': [
                        {
                            'content': '<jailbreak prompt> <adversarial question>',
                            'role': 'user'
                        },
                        {
                            'content': "<response from endpoint>",
                            'role': 'assistant',
                            'context': None
                        }
                    ],
                    '$schema': 'http://azureml/sdk-2-0/ChatConversation.json'
                }]
            }
        """
        if scenario not in AdversarialScenario.__members__.values():
            raise ValueError("Invalid adversarial scenario")
        jb_sim = AdversarialSimulator(azure_ai_project=self.azure_ai_project, credential=self.credential)
        jb_sim_results = await jb_sim(
            scenario=scenario,
            target=target,
            max_conversation_turns=max_conversation_turns,
            max_simulation_results=max_simulation_results,
            api_call_retry_limit=api_call_retry_limit,
            api_call_retry_sleep_sec=api_call_retry_sleep_sec,
            api_call_delay_sec=api_call_delay_sec,
            concurrent_async_task=concurrent_async_task,
            _jailbreak_type="xpia",
        )
        return jb_sim_results
