# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# flake8: noqa: F402
# pylint: skip-file
# needed for 'list' type annotations on 3.8
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import threading
from typing import Any, Callable, Dict, List, Optional, Union

from tqdm import tqdm

logger = logging.getLogger(__name__)

from promptflow.evals.synthetic.simulator import _template_dir as template_dir
from promptflow.evals.synthetic.simulator._conversation import ConversationBot, ConversationRole, simulate_conversation
from promptflow.evals.synthetic.simulator._model_tools import LLMBase, ManagedIdentityAPITokenManager
from promptflow.evals.synthetic.simulator._model_tools.models import (
    AsyncHTTPClientWithRetry,
    OpenAIChatCompletionsModel,
)
from promptflow.evals.synthetic.simulator._rai_rest_client.rai_client import RAIClient
from promptflow.evals.synthetic.simulator.simulator._callback_conversation_bot import CallbackConversationBot
from promptflow.evals.synthetic.simulator.simulator._proxy_completion_model import ProxyChatCompletionsModel
from promptflow.evals.synthetic.simulator.simulator._token_manager import PlainTokenManager, TokenScope
from promptflow.evals.synthetic.simulator.simulator._utils import JsonLineList
from promptflow.evals.synthetic.simulator.templates._simulator_templates import SimulatorTemplates, Template

BASIC_MD = os.path.join(template_dir, "basic.md")  # type: ignore[has-type]
USER_MD = os.path.join(template_dir, "user.md")  # type: ignore[has-type]


class Simulator:
    def __init__(
        self,
        *,
        simulator_connection: Dict = None,  # type: ignore[name-defined]
        ml_client: "MLClient" = None,  # type: ignore[name-defined]
        simulate_callback: Optional[Callable[[Dict], Dict]] = None,
    ):
        """
        Initialize the instance with the given parameters.

        :keyword simulator_connection: A dictionary containing the configuration for the openAI simulator connection.
            Mandatory keys: api_key, api_base, model_name, api_version
            Optional keys: model_kwargs
            Defaults to None.
        :paramtype simulator_connection: Optional[Dict]
        :keyword ml_client: An instance of MLClient for interacting with the AI service. Defaults to None.
        :paramtype ml_client: Optional[MLClient]
        :keyword simulate_callback: A callback function that takes a dictionary as input and returns a dictionary.
            This function is called to simulate the assistant response. Defaults to None.
        :paramtype simulate_callback: Optional[Callable[[Dict], Dict]]

        :raises ValueError: If `simulator_connection` and `ml_client` are not provided (i.e., they are None).
        """
        if (simulator_connection is None and ml_client is None) or (
            ml_client is not None and simulator_connection is not None
        ):
            raise ValueError("One and only one of the parameters [simulator_connection, ml_client] has to be set.")

        if simulate_callback is None:
            raise ValueError("Callback cannot be None.")

        if not asyncio.iscoroutinefunction(simulate_callback):
            raise ValueError("Callback has to be an async function.")

        self.simulator_connection = self._to_openai_chat_completion_model(simulator_connection)
        self.adversarial = False
        self.rai_client = None
        if ml_client:
            self.ml_client = ml_client
            self.token_manager = ManagedIdentityAPITokenManager(
                token_scope=TokenScope.DEFAULT_AZURE_MANAGEMENT,
                logger=logging.getLogger("managed identity token manager"),
            )
            self.rai_client = RAIClient(self.ml_client, self.token_manager)

        self.template_handler = SimulatorTemplates(self.rai_client)
        self.simulate_callback = simulate_callback

    def _get_user_proxy_completion_model(self, tkey, tparam):
        return ProxyChatCompletionsModel(
            name="raisvc_proxy_model",
            template_key=tkey,
            template_parameters=tparam,
            endpoint_url=self.rai_client.simulation_submit_endpoint,
            token_manager=self.token_manager,
            api_version="2023-07-01-preview",
            max_tokens=1200,
            temperature=0.0,
        )

    def _to_openai_chat_completion_model(self, config: Dict):  # type: ignore[name-defined]
        if config is None:
            return None
        #  validate the config object to have the required fields
        if "api_key" not in config:
            raise ValueError("api_key is required in the config object.")
        if "api_base" not in config:
            raise ValueError("api_base is required in the config object.")
        if "model_name" not in config:
            raise ValueError("model_name is required in the config object.")
        if "api_version" not in config:
            raise ValueError("api_version is required in the config object.")
        token_manager = PlainTokenManager(
            openapi_key=config.get("api_key"),
            auth_header="api-key",
            logger=logging.getLogger("bot_token_manager"),
        )
        return OpenAIChatCompletionsModel(
            endpoint_url=f"{config.get('api_base')}openai/deployments/{config.get('model_name')}/chat/completions",
            token_manager=token_manager,
            api_version=config.get("api_version"),
            name=config.get("model_name"),
            **config.get("model_kwargs", {}),
        )

    def _create_bot(
        self,
        role: ConversationRole,
        conversation_template: str,
        instantiation_parameters: dict,
        adversarial_template_key: Optional[str] = None,
        model: Union[LLMBase, OpenAIChatCompletionsModel] = None,  # type: ignore[arg-type,assignment]
    ):
        if role == ConversationRole.USER and self.adversarial:
            model = self._get_user_proxy_completion_model(
                tkey=adversarial_template_key, tparam=instantiation_parameters
            )

            return ConversationBot(
                role=role,
                model=model,
                conversation_template=conversation_template,
                instantiation_parameters=instantiation_parameters,
            )
        if role == ConversationRole.ASSISTANT:
            dummy_model = lambda: None  # pylint: disable=unnecessary-lambda-assignment # noqa: E731
            dummy_model.name = "dummy_model"  # type: ignore[attr-defined]
            return CallbackConversationBot(
                callback=self.simulate_callback,
                role=role,
                model=dummy_model,
                user_template=conversation_template,
                user_template_parameters=instantiation_parameters,
                conversation_template="",
                instantiation_parameters={},
            )

        return ConversationBot(
            role=role,
            model=model,
            conversation_template=conversation_template,
            instantiation_parameters=instantiation_parameters,
        )

    def _setup_bot(
        self,
        role: Union[str, ConversationRole],
        template: "Template",
        parameters: dict,
    ):
        if role == ConversationRole.ASSISTANT:
            return self._create_bot(role, str(template), parameters)
        if role == ConversationRole.USER:
            if template.content_harm:
                return self._create_bot(role, str(template), parameters, template.template_name)

            return self._create_bot(
                role,
                str(template),
                parameters,
                model=self.simulator_connection,
            )
        return None

    def _ensure_service_dependencies(self):
        if self.rai_client is None:
            raise ValueError("Simulation options require rai services but ai client is not provided.")

    def _join_conversation_starter(self, parameters, to_join):
        key = "conversation_starter"
        if key in parameters.keys():
            parameters[key] = f"{to_join} {parameters[key]}"
        else:
            parameters[key] = to_join

        return parameters

    async def simulate_async(
        self,
        *,
        template: "Template",
        max_conversation_turns: int = 1,
        parameters: Optional[List[dict]] = None,
        jailbreak: bool = False,
        api_call_retry_limit: int = 3,
        api_call_retry_sleep_sec: int = 1,  # pylint: disable=unused-argument
        api_call_delay_sec: float = 0,
        concurrent_async_task: int = 3,
        max_simulation_results: int = 3,
    ):
        """Asynchronously simulate conversations using the provided template and parameters

        :keyword template: An instance of the Template class defining the conversation structure.
        :paramtype template: Template
        :keyword max_conversation_turns: The maximum number of conversation turns to simulate.
            Defaults to 2, change only applies to chat templates.
        :paramtype max_conversation_turns: int
        :keyword parameters: A list of dictionaries containing the parameter values to be used in the simulations.
            Defaults to an empty list.
        :paramtype parameters: Optional[List[dict]]
        :keyword jailbreak: If set to True, allows breaking out of the conversation flow defined by the template.
            Defaults to False.
        :paramtype jailbreak: bool, optional
        :keyword api_call_retry_limit: The maximum number of API call retries in case of errors. Defaults to 3.
        :paramtype api_call_retry_limit: int, optional
        :keyword api_call_retry_sleep_sec: The time in seconds to wait between API call retries. Defaults to 1.
        :paramtype api_call_retry_sleep_sec: int, optional
        :keyword api_call_delay_sec: The time in seconds to wait between API calls. Defaults to 0.
        :paramtype api_call_delay_sec: float, optional
        :keyword concurrent_async_task: The maximum number of asynchronous tasks to run concurrently. Defaults to 3.
        :paramtype concurrent_async_task: int, optional
        :keyword max_simulation_results: The maximum number of simulation results to return. Defaults to 3.
        :paramtype max_simulation_results: int, optional

        :return: A list of dictionaries containing the simulation results.
        :rtype: List[Dict]

        Note: api_call_* parameters are only valid for simulation_connection defined.
        The parameters cannot be used to configure behavior for calling user provided callback.
        """
        if parameters is None:
            parameters = []
        if not isinstance(template, Template):
            raise ValueError(f"Please use simulator to construct template. Found {type(template)}")

        if not isinstance(parameters, list):
            raise ValueError(f"Expect parameters to be a list of dictionary, but found {type(parameters)}")
        if "conversation" not in template.template_name:
            max_conversation_turns = 2
        else:
            max_conversation_turns = max_conversation_turns * 2
        if template.content_harm:
            self._ensure_service_dependencies()
            self.adversarial = True
            # pylint: disable=protected-access
            templates = await self.template_handler._get_ch_template_collections(template.template_name)
        else:
            template.template_parameters = parameters
            templates = [template]
        concurrent_async_task = min(concurrent_async_task, 1000)
        semaphore = asyncio.Semaphore(concurrent_async_task)
        sim_results = []
        tasks = []
        total_tasks = sum(len(t.template_parameters) for t in templates)

        if max_simulation_results > total_tasks and self.adversarial:
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

        for t in templates:
            for p in t.template_parameters:
                if jailbreak:
                    self._ensure_service_dependencies()
                    jailbreak_dataset = await self.rai_client.get_jailbreaks_dataset()  # type: ignore[union-attr]
                    p = self._join_conversation_starter(p, random.choice(jailbreak_dataset))

                tasks.append(
                    asyncio.create_task(
                        self._simulate_async(
                            template=t,
                            parameters=p,
                            max_conversation_turns=max_conversation_turns,
                            api_call_retry_limit=api_call_retry_limit,
                            api_call_delay_sec=api_call_delay_sec,
                            api_call_retry_sleep_sec=api_call_retry_sleep_sec,
                            sem=semaphore,
                        )
                    )
                )

                if len(tasks) >= max_simulation_results:
                    break

            if len(tasks) >= max_simulation_results:
                break

        sim_results = []

        # Use asyncio.as_completed to update the progress bar when a task is complete
        for task in asyncio.as_completed(tasks):
            result = await task
            sim_results.append(result)  # Store the result
            progress_bar.update(1)

        progress_bar.close()

        return JsonLineList(sim_results)

    async def _simulate_async(
        self,
        *,
        template: "Template",
        max_conversation_turns: int,
        parameters: Optional[dict] = None,
        api_call_retry_limit: int = 3,
        api_call_retry_sleep_sec: int = 1,
        api_call_delay_sec: float = 0,
        sem: "asyncio.Semaphore" = asyncio.Semaphore(3),
    ) -> List[Dict]:
        """
        Asynchronously simulate conversations using the provided template and parameters.

        :param template: An instance of the Template class defining the conversation structure.
        :type template: Template
        :param max_conversation_turns: The maximum number of conversation turns to simulate.
        :type max_conversation_turns: int
        :param parameters: A list of dictionaries containing the parameter values to be used in the simulations.
        :type parameters: Optional[dict]
        :param api_call_retry_limit: The maximum number of API call retries in case of errors.
        :type api_call_retry_limit: int, optional
        :param api_call_retry_sleep_sec: The time in seconds to wait between API call retries.
        :type api_call_retry_sleep_sec: int, optional
        :param api_call_delay_sec: The time in seconds to wait between API calls.
        :type api_call_delay_sec: float, optional
        :param sem: The maximum number of asynchronous tasks to run concurrently.
        :type sem: asyncio.Semaphore, optional
        :return: A list of dictionaries containing the simulation results.
        :rtype: List[Dict]
        :raises Exception: If an error occurs during the simulation process.
        """
        if parameters is None:
            parameters = {}
        # create user bot
        user_bot = self._setup_bot(ConversationRole.USER, template, parameters)
        system_bot = self._setup_bot(ConversationRole.ASSISTANT, template, parameters)

        bots = [user_bot, system_bot]

        # simulate the conversation

        asyncHttpClient = AsyncHTTPClientWithRetry(
            n_retry=api_call_retry_limit,
            retry_timeout=api_call_retry_sleep_sec,
            logger=logger,
        )
        async with sem:
            async with asyncHttpClient.client as session:
                _, conversation_history = await simulate_conversation(
                    bots=bots,
                    session=session,
                    turn_limit=max_conversation_turns,
                    api_call_delay_sec=api_call_delay_sec,
                )

        return self._to_chat_protocol(template, conversation_history, parameters)

    def _get_citations(self, parameters, context_keys, turn_num=None):
        citations = []
        for c_key in context_keys:
            if isinstance(parameters[c_key], dict):
                if "callback_citation_key" in parameters[c_key]:
                    callback_citation_key = parameters[c_key]["callback_citation_key"]
                    callback_citations = self._get_callback_citations(
                        parameters[c_key][callback_citation_key], turn_num
                    )
                else:
                    callback_citations = []
                if callback_citations:
                    citations.extend(callback_citations)
                else:
                    for k, v in parameters[c_key].items():
                        if k not in ["callback_citations", "callback_citation_key"]:
                            citations.append({"id": k, "content": self._to_citation_content(v)})
            else:
                citations.append(
                    {
                        "id": c_key,
                        "content": self._to_citation_content(parameters[c_key]),
                    }
                )

        return {"citations": citations}

    def _to_citation_content(self, obj):
        if isinstance(obj, str):
            return obj
        return json.dumps(obj)

    def _get_callback_citations(self, callback_citations: dict, turn_num: Optional[int] = None):
        if turn_num is None:
            return []
        current_turn_citations = []
        current_turn_str = "turn_" + str(turn_num)
        if current_turn_str in callback_citations.keys():
            citations = callback_citations[current_turn_str]
            if isinstance(citations, dict):
                for k, v in citations.items():
                    current_turn_citations.append({"id": k, "content": self._to_citation_content(v)})
            else:
                current_turn_citations.append(
                    {
                        "id": current_turn_str,
                        "content": self._to_citation_content(citations),
                    }
                )
        return current_turn_citations

    def _to_chat_protocol(self, template, conversation_history, template_parameters):
        messages = []
        for i, m in enumerate(conversation_history):
            message = {"content": m.message, "role": m.role.value}
            if len(template.context_key) > 0:
                citations = self._get_citations(template_parameters, template.context_key, i)
                message["context"] = citations
            elif "context" in m.full_response:
                # adding context for adv_qa
                message["context"] = m.full_response["context"]
            messages.append(message)
        template_parameters["metadata"] = {}
        if "ch_template_placeholder" in template_parameters:
            del template_parameters["ch_template_placeholder"]

        return {
            "template_parameters": template_parameters,
            "messages": messages,
            "$schema": "http://azureml/sdk-2-0/ChatConversation.json",
        }

    def _wrap_async(
        self,
        results,
        template: "Template",
        max_conversation_turns: int,
        parameters: Optional[List[dict]] = None,
        jailbreak: bool = False,
        api_call_retry_limit: int = 3,
        api_call_retry_sleep_sec: int = 1,
        api_call_delay_sec: float = 0,
        concurrent_async_task: int = 1,
        max_simulation_results: int = 3,
    ):
        if parameters is None:
            parameters = []
        result = asyncio.run(
            self.simulate_async(
                template=template,
                parameters=parameters,
                max_conversation_turns=max_conversation_turns,
                jailbreak=jailbreak,
                api_call_retry_limit=api_call_retry_limit,
                api_call_retry_sleep_sec=api_call_retry_sleep_sec,
                api_call_delay_sec=api_call_delay_sec,
                max_simulation_results=max_simulation_results,
                concurrent_async_task=concurrent_async_task,
            )
        )
        results[0] = result

    def simulate(
        self,
        template: "Template",
        max_conversation_turns: int,
        parameters: Optional[List[dict]] = None,
        jailbreak: bool = False,
        api_call_retry_limit: int = 3,
        api_call_retry_sleep_sec: int = 1,
        api_call_delay_sec: float = 0,
        max_simulation_results: int = 3,
    ):
        """
        Simulates a conversation using a predefined template with customizable parameters and control over API behavior.

        :param template: The template object that defines the structure and flow of the conversation.
        :type template: Template
        :param max_conversation_turns: The maximum number of conversation turns to simulate.
        :type max_conversation_turns: int
        :param parameters: A list of dictionaries where each dictionary contains parameters specific to a single turn.
        :type parameters: Optional[List[dict]]
        :param jailbreak: A flag to determine if the simulation should continue when encountering API errors.
        :type jailbreak: bool, optional
        :param api_call_retry_limit: The maximum number of retries for API calls upon encountering an error.
        :type api_call_retry_limit: int, optional
        :param api_call_retry_sleep_sec: The number of seconds to wait between retry attempts of an API call.
        :type api_call_retry_sleep_sec: int, optional
        :param api_call_delay_sec: The number of seconds to wait
               before making a new API call to simulate conversation delay.
        :type api_call_delay_sec: float, optional
        :keyword max_simulation_results: The maximum number of simulation results to return. Defaults to 3.
        :paramtype max_simulation_results: int, optional
        :return: The outcome of the simulated conversations as a list.
        :rtype: List[Dict]
        """
        if parameters is None:
            parameters = []
        results = [None]
        concurrent_async_task = 1

        thread = threading.Thread(
            target=self._wrap_async,
            args=(
                results,
                template,
                max_conversation_turns,
                parameters,
                jailbreak,
                api_call_retry_limit,
                api_call_retry_sleep_sec,
                api_call_delay_sec,
                max_simulation_results,
                concurrent_async_task,
            ),
        )

        thread.start()
        thread.join()

        return results[0]

    @staticmethod
    def from_fn(
        *,
        fn: Callable[[Any], dict],
        simulator_connection: "AzureOpenAIModelConfiguration" = None,  # type: ignore[name-defined]
        ml_client: "MLClient" = None,  # type: ignore[name-defined]
        **kwargs,
    ):
        """
        Creates an instance from a function that defines certain behaviors or configurations,
        along with connections to simulation and AI services.

        :param fn: The function to be used for configuring or defining behavior.
                   This function should accept a single argument and return a dictionary of configurations.
        :type fn: Callable[[Any], dict]
        :param simulator_connection: Configuration for the connection to the simulation service, if any.
        :type simulator_connection: AzureOpenAIModelConfiguration, optional
        :keyword ml_client: An instance of MLClient for interacting with the AI service. Defaults to None.
        :paramtype ml_client: Optional[MLClient]
        :return: An instance of simulator configured with the specified function, simulation connection, and AI client.
        :rtype: Simulator
        :raises ValueError: If both `simulator_connection` and `ml_client` are not provided (i.e., both are None).

        Any additional keyword arguments (`**kwargs`) will be passed directly to the function `fn`.
        """
        if hasattr(fn, "__wrapped__"):
            func_module = fn.__wrapped__.__module__
            func_name = fn.__wrapped__.__name__
            if func_module == "openai.resources.chat.completions" and func_name == "create":
                return Simulator._from_openai_chat_completions(fn, simulator_connection, ml_client, **kwargs)
        return Simulator(
            simulator_connection=simulator_connection,
            ml_client=ml_client,
            simulate_callback=fn,
        )

    @staticmethod
    def _from_openai_chat_completions(fn: Callable[[Any], dict], simulator_connection=None, ml_client=None, **kwargs):
        return Simulator(
            simulator_connection=simulator_connection,
            ml_client=ml_client,
            simulate_callback=Simulator._wrap_openai_chat_completion(fn, **kwargs),
        )

    @staticmethod
    def _wrap_openai_chat_completion(fn, **kwargs):
        async def callback(chat_protocol_message):
            response = await fn(messages=chat_protocol_message["messages"], **kwargs)

            message = response.choices[0].message

            formatted_response = {"role": message.role, "content": message.content}

            chat_protocol_message["messages"].append(formatted_response)

            return chat_protocol_message

        return callback

    @staticmethod
    def from_pf_path(  # pylint: disable=unused-argument
        *,
        pf_path: str,
        simulator_connection: "AzureOpenAIModelConfiguration" = None,  # type: ignore[name-defined]
        ml_client: "MLClient" = None,  # type: ignore[name-defined]
        **kwargs,
    ):
        """
        Creates an instance of Simulator from a specified promptflow path.

        :param pf_path: The path to the promptflow folder
        :type pf_path: str
        :param simulator_connection: Configuration for the connection to the simulation service, if any.
        :type simulator_connection: AzureOpenAIModelConfiguration, optional
        :keyword ml_client: An instance of MLClient for interacting with the AI service. Defaults to None.
        :paramtype ml_client: Optional[MLClient]
        :return: An instance of the class configured with the specified policy file,
                 simulation connection, and AI client.
        :rtype: The class which this static method is part of.
        :return: An instance of simulator configured with the specified function, simulation connection, and AI client.
        :rtype: Simulator
        :raises ValueError: If both `simulator_connection` and `ml_client` are not provided (i.e., both are None).

        Any additional keyword arguments (`**kwargs`) will be passed to the underlying configuration
        or initialization methods.
        """
        try:
            from promptflow.client import load_flow
        except EnvironmentError as env_err:
            raise EnvironmentError(
                "Unable to import from promptflow. Have you installed promptflow in the python environment?"
            ) from env_err
        flow = load_flow(pf_path)
        return Simulator(
            simulator_connection=simulator_connection,
            ml_client=ml_client,
            simulate_callback=Simulator._wrap_pf(flow),
        )

    @staticmethod
    def _wrap_pf(flow):
        flow_ex = flow._init_executable()  # pylint: disable=protected-access
        for k, v in flow_ex.inputs.items():
            if v.is_chat_history:
                chat_history_key = k
                if v.type.value != "list":
                    raise TypeError(f"Chat history {k} not a list.")

            if v.is_chat_input:
                chat_input_key = k
                if v.type.value != "string":
                    raise TypeError(f"Chat input {k} not a string.")

        for k, v in flow_ex.outputs.items():
            if v.is_chat_output:
                chat_output_key = k
                if v.type.value != "string":
                    raise TypeError(f"Chat output {k} not a string.")

        if chat_output_key is None or chat_input_key is None:
            raise ValueError("Prompflow has no required chat input and/or chat output.")

        async def callback(chat_protocol_message):
            all_messages = chat_protocol_message["messages"]
            input_data = {chat_input_key: all_messages[-1]}
            if chat_history_key:
                input_data[chat_history_key] = all_messages

            response = flow.invoke(input_data).output
            chat_protocol_message["messages"].append({"role": "assistant", "content": response[chat_output_key]})

            return chat_protocol_message

        return callback

    @staticmethod
    def create_template(
        name: str,
        template: Optional[str],
        template_path: Optional[str],
        context_key: Optional[list[str]],
    ):
        """
        Creates a template instance either from a string or from a file path provided.

        :param name: The name to assign to the created template.
        :type name: str
        :param template: The string representation of the template content.
        :type template: Optional[str]
        :param template_path: The file system path to a file containing the template content.
        :type template_path: Optional[str]
        :param context_key: A list of keys that define the context used within the template.
        :type context_key: Optional[list[str]]
        :return: A new instance of a Template configured with the provided details.
        :rtype: Template

        :raises ValueError: If both or neither of the parameters 'template' and 'template_path' are set.

        One of 'template' or 'template_path' must be provided to create a template. If 'template' is provided,
        it is used directly; if 'template_path' is provided, the content is read from the file at that path.
        """
        if (template is None and template_path is None) or (template is not None and template_path is not None):
            raise ValueError("One and only one of the parameters [template, template_path] has to be set.")

        if template is not None:
            return Template(template_name=name, text=template, context_key=context_key)

        if template_path is not None:
            with open(template_path, "r", encoding="utf-8") as f:
                tc = f.read()

            return Template(template_name=name, text=tc, context_key=context_key)

        raise ValueError("Condition not met for creating template, please check examples and parameter list.")

    @staticmethod
    def get_template(template_name: str):
        """
        Retrieves a template instance by its name.

        :param template_name: The name of the template to retrieve.
        :type template_name: str
        :return: The Template instance corresponding to the given name.
        :rtype: Template
        """
        st = SimulatorTemplates()
        return st.get_template(template_name)
