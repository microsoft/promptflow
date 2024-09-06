# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# noqa: E501
import asyncio
import functools
import logging
import random
from typing import Any, Callable, Dict, List, Optional

from azure.core.pipeline.policies import AsyncRetryPolicy, RetryMode
from azure.identity import DefaultAzureCredential
from tqdm import tqdm

from promptflow._sdk._telemetry import ActivityType, monitor_operation
from promptflow.evals._http_utils import get_async_http_client
from promptflow.evals.synthetic.adversarial_scenario import AdversarialScenario, _UnstableAdversarialScenario

from ._conversation import CallbackConversationBot, ConversationBot, ConversationRole
from ._conversation._conversation import simulate_conversation
from ._model_tools import (
    AdversarialTemplateHandler,
    ManagedIdentityAPITokenManager,
    ProxyChatCompletionsModel,
    RAIClient,
    TokenScope,
)
from ._utils import JsonLineList

logger = logging.getLogger(__name__)


def monitor_adversarial_scenario(func) -> Callable:
    """Monitor an adversarial scenario with logging

    :param func: The function to be monitored
    :type func: Callable
    :return: The decorated function
    :rtype: Callable
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        scenario = str(kwargs.get("scenario", None))
        max_conversation_turns = kwargs.get("max_conversation_turns", None)
        max_simulation_results = kwargs.get("max_simulation_results", None)
        _jailbreak_type = kwargs.get("_jailbreak_type", None)
        decorated_func = monitor_operation(
            activity_name="adversarial.simulator.call",
            activity_type=ActivityType.PUBLICAPI,
            custom_dimensions={
                "scenario": scenario,
                "max_conversation_turns": max_conversation_turns,
                "max_simulation_results": max_simulation_results,
                "_jailbreak_type": _jailbreak_type,
            },
        )(func)

        return decorated_func(*args, **kwargs)

    return wrapper


class AdversarialSimulator:
    """
    Initializes the adversarial simulator with a project scope.

    :param azure_ai_project: Dictionary defining the scope of the project. It must include the following keys:
        - "subscription_id": Azure subscription ID.
        - "resource_group_name": Name of the Azure resource group.
        - "project_name": Name of the Azure Machine Learning workspace.
    :param credential: The credential for connecting to Azure AI project.
    :type credential: ~azure.core.credentials.TokenCredential
    :type azure_ai_project: Dict[str, Any]
    """

    def __init__(self, *, azure_ai_project: Dict[str, Any], credential=None):
        """Constructor."""
        # check if azure_ai_project has the keys: subscription_id, resource_group_name and project_name
        if not all(key in azure_ai_project for key in ["subscription_id", "resource_group_name", "project_name"]):
            raise ValueError("azure_ai_project must contain keys: subscription_id, resource_group_name, project_name")
        # check the value of the keys in azure_ai_project is not none
        if not all(azure_ai_project[key] for key in ["subscription_id", "resource_group_name", "project_name"]):
            raise ValueError("subscription_id, resource_group_name and project_name must not be None")
        if "credential" not in azure_ai_project and not credential:
            credential = DefaultAzureCredential()
        elif "credential" in azure_ai_project:
            credential = azure_ai_project["credential"]
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
        # Note: the scenario input also accepts inputs from _PrivateAdversarialScenario, but that's
        # not stated since those values are nominally for internal use only.
        scenario: AdversarialScenario,
        target: Callable,
        max_conversation_turns: int = 1,
        max_simulation_results: int = 3,
        api_call_retry_limit: int = 3,
        api_call_retry_sleep_sec: int = 1,
        api_call_delay_sec: int = 0,
        concurrent_async_task: int = 3,
        _jailbreak_type: Optional[str] = None,
        randomize_order: bool = True,
        randomization_seed: Optional[int] = None,
    ):
        """
        Executes the adversarial simulation against a specified target function asynchronously.

        :keyword scenario: Enum value specifying the adversarial scenario used for generating inputs.
         example:

         - :py:const:`promptflow.evals.synthetic.adversarial_scenario.AdversarialScenario.ADVERSARIAL_QA`
         - :py:const:`promptflow.evals.synthetic.adversarial_scenario.AdversarialScenario.ADVERSARIAL_CONVERSATION`
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
        :keyword randomize_order: Whether or not the order of the prompts should be randomized. Defaults to True.
        :paramtype randomize_order: bool
        :keyword randomization_seed: The seed used to randomize prompt selection. If unset, the system's
            default seed is used. Defaults to None.
        :paramtype randomization_seed: Optional[int]
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
                }
            ]
        """

        # validate the inputs
        if scenario != AdversarialScenario.ADVERSARIAL_CONVERSATION:
            max_conversation_turns = 2
        else:
            max_conversation_turns = max_conversation_turns * 2
        if not (
            scenario in AdversarialScenario.__members__.values()
            or scenario in _UnstableAdversarialScenario.__members__.values()
        ):
            raise ValueError("Invalid adversarial scenario")
        self._ensure_service_dependencies()
        templates = await self.adversarial_template_handler._get_content_harm_template_collections(scenario.value)
        concurrent_async_task = min(concurrent_async_task, 1000)
        semaphore = asyncio.Semaphore(concurrent_async_task)
        sim_results = []
        tasks = []
        total_tasks = sum(len(t.template_parameters) for t in templates)
        if max_simulation_results > total_tasks:
            logger.warning(
                "Cannot provide %s results due to maximum number of adversarial simulations that can be generated: %s."
                "\n %s simulations will be generated.",
                max_simulation_results,
                total_tasks,
                total_tasks,
            )
        total_tasks = min(total_tasks, max_simulation_results)
        if _jailbreak_type:
            jailbreak_dataset = await self.rai_client.get_jailbreaks_dataset(type=_jailbreak_type)
        progress_bar = tqdm(
            total=total_tasks,
            desc="generating jailbreak simulations" if _jailbreak_type else "generating simulations",
            ncols=100,
            unit="simulations",
        )
        for template in templates:
            parameter_order = list(range(len(template.template_parameters)))
            if randomize_order:
                # The template parameter lists are persistent across sim runs within a session,
                # So randomize a the selection instead of the parameter list directly,
                # or a potentially large deep copy.
                if randomization_seed is not None:
                    random.seed(randomization_seed)
                random.shuffle(parameter_order)
            for index in parameter_order:
                parameter = template.template_parameters[index].copy()
                if _jailbreak_type == "upia":
                    parameter = self._join_conversation_starter(parameter, random.choice(jailbreak_dataset))
                tasks.append(
                    asyncio.create_task(
                        self._simulate_async(
                            target=target,
                            template=template,
                            parameters=parameter,
                            max_conversation_turns=max_conversation_turns,
                            api_call_retry_limit=api_call_retry_limit,
                            api_call_retry_sleep_sec=api_call_retry_sleep_sec,
                            api_call_delay_sec=api_call_delay_sec,
                            semaphore=semaphore,
                        )
                    )
                )
                if len(tasks) >= max_simulation_results:
                    break
            if len(tasks) >= max_simulation_results:
                break
        for task in asyncio.as_completed(tasks):
            sim_results.append(await task)
            progress_bar.update(1)
        progress_bar.close()

        return JsonLineList(sim_results)

    def _to_chat_protocol(self, *, conversation_history, template_parameters: Dict = None):
        if template_parameters is None:
            template_parameters = {}
        messages = []
        for _, m in enumerate(conversation_history):
            message = {"content": m.message, "role": m.role.value}
            if "context" in m.full_response:
                message["context"] = m.full_response["context"]
            messages.append(message)
        conversation_category = template_parameters.pop("metadata", {}).get("Category")
        template_parameters["metadata"] = {}
        for key in (
            "conversation_starter",
            "group_of_people",
            "target_population",
            "topic",
            "ch_template_placeholder",
        ):
            template_parameters.pop(key, None)
        if conversation_category:
            template_parameters["category"] = conversation_category
        return {
            "template_parameters": template_parameters,
            "messages": messages,
            "$schema": "http://azureml/sdk-2-0/ChatConversation.json",
        }

    async def _simulate_async(
        self,
        *,
        target: Callable,
        template,
        parameters,
        max_conversation_turns,
        api_call_retry_limit,
        api_call_retry_sleep_sec,
        api_call_delay_sec,
        semaphore,
    ) -> List[Dict]:
        user_bot = self._setup_bot(role=ConversationRole.USER, template=template, parameters=parameters)
        system_bot = self._setup_bot(
            target=target, role=ConversationRole.ASSISTANT, template=template, parameters=parameters
        )
        bots = [user_bot, system_bot]
        session = get_async_http_client().with_policies(
            retry_policy=AsyncRetryPolicy(
                retry_total=api_call_retry_limit,
                retry_backoff_factor=api_call_retry_sleep_sec,
                retry_mode=RetryMode.Fixed,
            )
        )

        async with semaphore:
            _, conversation_history = await simulate_conversation(
                bots=bots,
                session=session,
                turn_limit=max_conversation_turns,
                api_call_delay_sec=api_call_delay_sec,
            )
        return self._to_chat_protocol(conversation_history=conversation_history, template_parameters=parameters)

    def _get_user_proxy_completion_model(self, template_key, template_parameters):
        return ProxyChatCompletionsModel(
            name="raisvc_proxy_model",
            template_key=template_key,
            template_parameters=template_parameters,
            endpoint_url=self.rai_client.simulation_submit_endpoint,
            token_manager=self.token_manager,
            api_version="2023-07-01-preview",
            max_tokens=1200,
            temperature=0.0,
        )

    def _setup_bot(self, *, role, template, parameters, target: Callable = None):
        if role == ConversationRole.USER:
            model = self._get_user_proxy_completion_model(
                template_key=template.template_name, template_parameters=parameters
            )
            return ConversationBot(
                role=role,
                model=model,
                conversation_template=str(template),
                instantiation_parameters=parameters,
            )

        if role == ConversationRole.ASSISTANT:
            dummy_model = lambda: None  # noqa: E731
            dummy_model.name = "dummy_model"
            return CallbackConversationBot(
                callback=target,
                role=role,
                model=dummy_model,
                user_template=str(template),
                user_template_parameters=parameters,
                conversation_template="",
                instantiation_parameters={},
            )
        return ConversationBot(
            role=role,
            model=model,
            conversation_template=template,
            instantiation_parameters=parameters,
        )

    def _join_conversation_starter(self, parameters, to_join):
        key = "conversation_starter"
        if key in parameters.keys():
            parameters[key] = f"{to_join} {parameters[key]}"
        else:
            parameters[key] = to_join

        return parameters

    def call_sync(
        self,
        *,
        max_conversation_turns: int,
        max_simulation_results: int,
        target: Callable,
        api_call_retry_limit: int,
        api_call_retry_sleep_sec: int,
        api_call_delay_sec: int,
        concurrent_async_task: int,
    ) -> List[Dict[str, Any]]:
        """Call the adversarial simulator synchronously.

        :keyword max_conversation_turns: The maximum number of conversation turns to simulate.
        :paramtype max_conversation_turns: int
        :keyword max_simulation_results: The maximum number of simulation results to return.
        :paramtype max_simulation_results: int
        :keyword target: The target function to simulate adversarial inputs against.
        :paramtype target: Callable
        :keyword api_call_retry_limit: The maximum number of retries for each API call within the simulation.
        :paramtype api_call_retry_limit: int
        :keyword api_call_retry_sleep_sec: The sleep duration (in seconds) between retries for API calls.
        :paramtype api_call_retry_sleep_sec: int
        :keyword api_call_delay_sec: The delay (in seconds) before making an API call.
        :paramtype api_call_delay_sec: int
        :keyword concurrent_async_task: The number of asynchronous tasks to run concurrently during the simulation.
        :paramtype concurrent_async_task: int
        :return: A list of dictionaries, each representing a simulated conversation.
        :rtype: List[Dict[str, Any]]
        """
        # Running the async method in a synchronous context
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If the loop is already running, use run_until_complete
            # Note: This approach might not be suitable in all contexts, especially with nested async calls
            future = asyncio.ensure_future(
                self(
                    max_conversation_turns=max_conversation_turns,
                    max_simulation_results=max_simulation_results,
                    target=target,
                    api_call_retry_limit=api_call_retry_limit,
                    api_call_retry_sleep_sec=api_call_retry_sleep_sec,
                    api_call_delay_sec=api_call_delay_sec,
                    concurrent_async_task=concurrent_async_task,
                )
            )
            return loop.run_until_complete(future)

        # If no event loop is running, use asyncio.run (Python 3.7+)
        return asyncio.run(
            self(
                max_conversation_turns=max_conversation_turns,
                max_simulation_results=max_simulation_results,
                target=target,
                api_call_retry_limit=api_call_retry_limit,
                api_call_retry_sleep_sec=api_call_retry_sleep_sec,
                api_call_delay_sec=api_call_delay_sec,
                concurrent_async_task=concurrent_async_task,
            )
        )
