# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# noqa: E501
import asyncio
import functools
import logging
import random
from typing import Any, Callable, Dict, List

from tqdm import tqdm

from promptflow._sdk._telemetry import ActivityType, monitor_operation
from promptflow.evals.synthetic.adversarial_scenario import AdversarialScenario

from ._conversation import CallbackConversationBot, ConversationBot, ConversationRole
from ._conversation._conversation import simulate_conversation
from ._model_tools import (
    AdversarialTemplateHandler,
    AsyncHTTPClientWithRetry,
    ManagedIdentityAPITokenManager,
    ProxyChatCompletionsModel,
    RAIClient,
    TokenScope,
)
from ._utils import JsonLineList

logger = logging.getLogger(__name__)


def monitor_adversarial_scenario(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        scenario = str(kwargs.get("scenario", None))
        max_conversation_turns = kwargs.get("max_conversation_turns", None)
        max_simulation_results = kwargs.get("max_simulation_results", None)
        jailbreak = kwargs.get("jailbreak", None)
        decorated_func = monitor_operation(
            activity_name="adversarial.simulator.call",
            activity_type=ActivityType.PUBLICAPI,
            custom_dimensions={
                "scenario": scenario,
                "max_conversation_turns": max_conversation_turns,
                "max_simulation_results": max_simulation_results,
                "jailbreak": jailbreak,
            },
        )(func)

        return decorated_func(*args, **kwargs)

    return wrapper


class AdversarialSimulator:
    def __init__(self, *, azure_ai_project: Dict[str, Any]):
        """
        Initializes the adversarial simulator with a project scope.

        :param azure_ai_project: Dictionary defining the scope of the project. It must include the following keys:
            - "subscription_id": Azure subscription ID.
            - "resource_group_name": Name of the Azure resource group.
            - "project_name": Name of the Azure Machine Learning workspace.
            - "credential": Azure credentials object for authentication.
        :type azure_ai_project: Dict[str, Any]
        """
        # check if azure_ai_project has the keys: subscription_id, resource_group_name, project_name, credential
        if not all(
            key in azure_ai_project for key in ["subscription_id", "resource_group_name", "project_name", "credential"]
        ):
            raise ValueError(
                "azure_ai_project must contain keys: subscription_id, resource_group_name, project_name, credential"
            )
        # check the value of the keys in azure_ai_project is not none
        if not all(
            azure_ai_project[key] for key in ["subscription_id", "resource_group_name", "project_name", "credential"]
        ):
            raise ValueError("subscription_id, resource_group_name, project_name, and credential must not be None")
        self.azure_ai_project = azure_ai_project
        self.token_manager = ManagedIdentityAPITokenManager(
            token_scope=TokenScope.DEFAULT_AZURE_MANAGEMENT,
            logger=logging.getLogger("AdversarialSimulator"),
            credential=self.azure_ai_project["credential"],
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
        jailbreak: bool = False,
    ):
        """
        Executes the adversarial simulation against a specified target function asynchronously.

        :param scenario: Enum value specifying the adversarial scenario used for generating inputs.
        :type scenario: AdversarialScenario
        :example: AdversarialScenario.ADVERSARIAL_QA, AdversarialScenario.ADVERSARIAL_CONVERSATION
        :param target: The target function to simulate adversarial inputs against.
        This function should be asynchronous and accept a dictionary representing the adversarial input.
        :type target: Callable
        :param max_conversation_turns: The maximum number of conversation turns to simulate.
        Defaults to 1.
        :type max_conversation_turns: int
        :param max_simulation_results: The maximum number of simulation results to return.
        Defaults to 3.
        :type max_simulation_results: int
        :param api_call_retry_limit: The maximum number of retries for each API call within the simulation.
        Defaults to 3.
        :type api_call_retry_limit: int
        :param api_call_retry_sleep_sec: The sleep duration (in seconds) between retries for API calls.
        Defaults to 1 second.
        :type api_call_retry_sleep_sec: int
        :param api_call_delay_sec: The delay (in seconds) before making an API call.
        This can be used to avoid hitting rate limits. Defaults to 0 seconds.
        :type api_call_delay_sec: int
        :param concurrent_async_task: The number of asynchronous tasks to run concurrently during the simulation.
        Defaults to 3.
        :type concurrent_async_task: int
        :param jailbreak: If set to True, allows breaking out of the conversation flow defined by the scenario.
        Defaults to False.
        :type jailbreak: bool
        :return: A list of dictionaries, each representing a simulated conversation. Each dictionary contains:
         - 'template_parameters': A dictionary with parameters used in the conversation template,
            including 'conversation_starter'.
         - 'messages': A list of dictionaries, each representing a turn in the conversation.
            Each message dictionary includes 'content' (the message text) and
            'role' (indicating whether the message is from the 'user' or the 'assistant').
         - '$schema': A string indicating the schema URL for the conversation format.
         The 'content' for 'assistant' role messages may includes the messages that your callback returned.
        :rtype: List[Dict[str, Any]]
        """
        # validate the inputs
        if scenario != AdversarialScenario.ADVERSARIAL_CONVERSATION:
            max_conversation_turns = 2
        else:
            max_conversation_turns = max_conversation_turns * 2
        if scenario not in AdversarialScenario.__members__.values():
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
        progress_bar = tqdm(
            total=total_tasks,
            desc="generating simulations",
            ncols=100,
            unit="simulations",
        )
        for template in templates:
            for parameter in template.template_parameters:
                if jailbreak:
                    jailbreak_dataset = await self.rai_client.get_jailbreaks_dataset()
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

    def _to_chat_protocol(self, *, conversation_history, template_parameters):
        messages = []
        for i, m in enumerate(conversation_history):
            message = {"content": m.message, "role": m.role.value}
            if "context" in m.full_response:
                message["context"] = m.full_response["context"]
            messages.append(message)
        template_parameters["metadata"] = {}
        for key in (
            "conversation_starter",
            "group_of_people",
            "metadata",
            "target_population",
            "topic",
            "ch_template_placeholder",
        ):
            template_parameters.pop(key, None)

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
        asyncHttpClient = AsyncHTTPClientWithRetry(
            n_retry=api_call_retry_limit,
            retry_timeout=api_call_retry_sleep_sec,
            logger=logger,
        )
        async with semaphore:
            async with asyncHttpClient.client as session:
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
    ):
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
        else:
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
