# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import abc
import copy
import re
from os import PathLike
from pathlib import Path
from typing import Any, Mapping, Union

from promptflow._constants import DEFAULT_ENCODING, LANGUAGE_KEY, PROMPTY_EXTENSION, FlowLanguage
from promptflow._utils.flow_utils import is_flex_flow, is_prompty_flow, resolve_flow_path
from promptflow._utils.yaml_utils import load_yaml_string
from promptflow.contracts.tool import ValueType
from promptflow.core._errors import MissingRequiredInputError
from promptflow.core._prompty_utils import (
    convert_to_chat_list,
    find_referenced_image_set,
    get_connection,
    get_open_ai_client_by_connection,
    parse_chat,
    preprocess_template_string,
)
from promptflow.core._serving.flow_invoker import AsyncFlowInvoker, FlowInvoker
from promptflow.core._utils import init_executable, render_jinja_template_content
from promptflow.exceptions import UserErrorException


class FlowBase(abc.ABC):
    def __init__(self, *, data: dict, code: Path, path: Path, **kwargs):
        # yaml content if provided
        self._data = data
        # working directory of the flow
        self._code = Path(code).resolve()
        # flow file path, can be script file or flow definition YAML file
        self._path = Path(path).resolve()

    @property
    def code(self) -> Path:
        """Working directory of the flow."""
        return self._code

    @property
    def path(self) -> Path:
        """Flow file path. Can be script file or flow definition YAML file."""
        return self._path

    @classmethod
    def load(
        cls,
        source: Union[str, PathLike],
        **kwargs,
    ) -> "Flow":
        """
        Load flow from YAML file.

        :param source: The local yaml source of a flow. Must be a path to a local file.
            If the source is a path, it will be open and read.
            An exception is raised if the file does not exist.
        :type source: Union[PathLike, str]
        :return: A Flow object
        :rtype: Flow
        """
        flow_dir, flow_filename = resolve_flow_path(source)
        flow_path = flow_dir / flow_filename
        if is_prompty_flow(flow_path):
            return Prompty.load(source=flow_path, **kwargs)

        with open(flow_path, "r", encoding=DEFAULT_ENCODING) as f:
            flow_content = f.read()
            data = load_yaml_string(flow_content)
        flow_language = data.get(LANGUAGE_KEY, FlowLanguage.Python)
        if flow_language != FlowLanguage.Python:
            raise UserErrorException(
                message_format="Only python flows are allowed to be loaded with "
                "promptflow-core but got a {language} flow",
                language=flow_language,
            )

        if is_flex_flow(yaml_dict=data, working_dir=flow_dir):
            raise UserErrorException("Please call entry directly for flex flow.")
        return cls._create(code=flow_dir, path=flow_path, data=data)

    @classmethod
    def _create(cls, data, code, path, **kwargs):
        raise NotImplementedError()


class Flow(FlowBase):
    """A Flow in the context of PromptFlow is a sequence of steps that define a task.
    Each step in the flow could be a prompt that is sent to a language model, or simply a function task,
    and the output of one step can be used as the input to the next.
    Flows can be used to build complex applications with language models.

    Example:

    .. code-block:: python

        from promptflow.core import Flow
        flow = Flow.load(source="path/to/flow.yaml")
        result = flow(input_a=1, input_b=2)

    """

    def __call__(self, *args, **kwargs) -> Mapping[str, Any]:
        """Calling flow as a function, the inputs should be provided with key word arguments.
        Returns the output of the flow.
        The function call throws UserErrorException: if the flow is not valid or the inputs are not valid.
        SystemErrorException: if the flow execution failed due to unexpected executor error.

        :param args: positional arguments are not supported.
        :param kwargs: flow inputs with key word arguments.
        :return:
        """

        if args:
            raise UserErrorException("Flow can only be called with keyword arguments.")

        result = self.invoke(inputs=kwargs)
        return result.output

    def invoke(self, inputs: dict, connections: dict = None, **kwargs) -> "LineResult":
        """Invoke a flow and get a LineResult object."""
        # candidate parameters: connections, variant, overrides, streaming

        invoker = FlowInvoker(
            flow=init_executable(flow_dag=self._data, working_dir=self.code),
            # TODO (3027983): resolve the connections before passing to invoker
            connections=connections,
            streaming=True,
            flow_path=self.path,
            working_dir=self.code,
        )
        result = invoker._invoke(
            data=inputs,
        )
        return result

    @classmethod
    def _create(cls, data, code, path, **kwargs):
        return cls(code=code, path=path, data=data, **kwargs)


class AsyncFlow(FlowBase):
    """Async flow is based on Flow, which is used to invoke flow in async mode.

    Example:

    .. code-block:: python

        from promptflow.core import class AsyncFlow
        flow = AsyncFlow.load(source="path/to/flow.yaml")
        result = await flow(input_a=1, input_b=2)

    """

    async def __call__(self, *args, **kwargs) -> Mapping[str, Any]:
        """Calling flow as a function in async, the inputs should be provided with key word arguments.
        Returns the output of the flow.
        The function call throws UserErrorException: if the flow is not valid or the inputs are not valid.
        SystemErrorException: if the flow execution failed due to unexpected executor error.

        :param args: positional arguments are not supported.
        :param kwargs: flow inputs with key word arguments.
        :return:
        """
        if args:
            raise UserErrorException("Flow can only be called with keyword arguments.")

        result = await self.invoke(inputs=kwargs)
        return result.output

    async def invoke(self, inputs: dict, *, connections: dict = None, **kwargs) -> "LineResult":
        """Invoke a flow and get a LineResult object."""

        invoker = AsyncFlowInvoker(
            flow=init_executable(flow_dag=self._data, working_dir=self.code),
            # TODO (3027983): resolve the connections before passing to invoker
            connections=connections,
            streaming=True,
            flow_path=self.path,
            working_dir=self.code,
        )
        result = await invoker._invoke_async(
            data=inputs,
        )
        return result

    @classmethod
    def _create(cls, data, code, path, **kwargs):
        return cls(code=code, path=path, data=data, **kwargs)


class Prompty(FlowBase):
    """A prompty is a prompt with predefined metadata like inputs, and can be executed directly like a flow.
    A prompty is represented as a templated markdown file with a modified front matter.
    The front matter is a yaml file that contains meta fields like connection, parameters, inputs, etc..

    Prompty example:
    .. code-block:: yaml

        ---
        name: Hello Prompty
        description: A basic prompt
        api: chat
        connection: connection_name
        parameters:
          deployment_name: gpt-35-turbo
          max_tokens: 128
          temperature: 0.2
        inputs:
          text:
            type: string
        ---
        system:
        Write a simple {{text}} program that displays the greeting message.

    Prompty as function example:
    .. code-block:: python

        from promptflow.core import Prompty
        prompty = Prompty.load(source="path/to/prompty.prompty")
        result = prompty(input_a=1, input_b=2)

    """

    def __init__(
        self,
        path: Union[str, PathLike],
        api: str = None,
        connection: Union[str, dict] = None,
        parameters: dict = None,
        **kwargs,
    ):
        # prompty file path
        path = Path(path)
        configs, self._template = self._parse_prompty(path)
        configs["api"] = api or configs.get("api", "chat")
        configs["connection"] = connection or configs.get("connection", None)
        if parameters:
            if configs.get("parameters", {}):
                configs["parameters"].update(parameters)
            else:
                configs["parameters"] = parameters
        for k in list(kwargs.keys()):
            if k in configs:
                value = kwargs.pop(k)
                if isinstance(value, dict):
                    configs[k].update(value)
                else:
                    configs[k] = value
        configs["inputs"] = self._resolve_inputs(configs.get("inputs", {}))
        self._connection = configs["connection"]
        self._parameters = configs["parameters"]
        self._api = configs["api"]
        self._inputs = configs["inputs"]
        super().__init__(code=path.parent, path=path, data=configs, content_hash=None, **kwargs)

    @classmethod
    def _load(cls, path: Path, **kwargs):
        return cls(path=path, **kwargs)

    # region overrides
    @classmethod
    def load(
        cls,
        source: Union[str, PathLike],
        raise_error=True,
        **kwargs,
    ) -> "Prompty":
        """
        Direct load non-dag flow from prompty file.

        :param source: The local prompt file. Must be a path to a local file.
            If the source is a path, it will be open and read.
            An exception is raised if the file does not exist.
        :type source: Union[PathLike, str]
        :param raise_error: Argument for non-dag flow raise validation error on unknown fields.
        :type raise_error: bool
        :return: A Prompty object
        :rtype: Prompty
        """
        source_path = Path(source)
        if not source_path.exists():
            raise UserErrorException(f"Source {source_path.absolute().as_posix()} does not exist")

        if source_path.suffix != PROMPTY_EXTENSION:
            raise UserErrorException("Source must be a file with .prompty extension.")
        return cls._load(path=source_path, **kwargs)

    @staticmethod
    def _parse_prompty(path):
        """ """
        with open(path, "r", encoding=DEFAULT_ENCODING) as f:
            prompty_content = f.read()
        pattern = r"-{3,}\n(.*)-{3,}\n(.*)"
        result = re.search(pattern, prompty_content, re.DOTALL)
        if not result:
            raise UserErrorException(
                "Illegal formatting of prompty. The prompt file is in markdown format and can be divided into two "
                "parts, the first part is in YAML format and contains connection and model information. The second "
                "part is the prompt template."
            )
        config_content, prompt_template = result.groups()
        configs = load_yaml_string(config_content)
        return configs, prompt_template

    def _resolve_inputs(self, inputs):
        resolved_inputs = {}
        for k, v in inputs.items():
            if isinstance(v, dict):
                resolved_inputs[k] = v
            else:
                resolved_inputs[k] = {"type": ValueType.from_value(v).value, "default": v}
        return resolved_inputs

    def _validate_inputs(self, input_values):
        resolved_inputs = {}
        missing_inputs = []
        for input_name, value in self._inputs.items():
            if input_name not in input_values and "default" not in value:
                missing_inputs.append(input_name)
                continue
            resolved_inputs[input_name] = input_values.get(input_name, value.get("default", None))
        if missing_inputs:
            raise MissingRequiredInputError(f"Missing required inputs: {missing_inputs}")
        return resolved_inputs

    def __call__(self, *args, **kwargs):
        """Calling flow as a function, the inputs should be provided with key word arguments.
        Returns the output of the prompty.
        The function call throws UserErrorException: if the flow is not valid or the inputs are not valid.
        SystemErrorException: if the flow execution failed due to unexpected executor error.

        :param args: positional arguments are not supported.
        :param kwargs: flow inputs with key word arguments.
        :return:
        """
        from promptflow.core._connection import AzureOpenAIConnection

        if args:
            raise UserErrorException("Prompty can only be called with keyword arguments.")
        # 1. init client
        connection = get_connection(self._connection)
        api_client = get_open_ai_client_by_connection(connection=connection)

        # 2. prepare params
        # TODO validate function in params
        params = copy.copy(self._parameters)
        if isinstance(connection, AzureOpenAIConnection):
            params["model"] = params.pop("deployment_name")
            params["extra_headers"] = {"ms-azure-ai-promptflow-called-from": "promptflow-core"}

        # 3.deal with prompt
        inputs = self._validate_inputs(kwargs)
        prompt = preprocess_template_string(self._template)
        referenced_images = find_referenced_image_set(inputs)

        # convert list type into ChatInputList type
        converted_kwargs = convert_to_chat_list(inputs)
        rendered_prompt = render_jinja_template_content(
            template_content=prompt, trim_blocks=True, keep_trailing_newline=True, **converted_kwargs
        )
        if self._api == "completion":
            params["prompt"] = rendered_prompt
            return api_client.completions.create(**params).choices[0].text
        else:
            params["messages"] = parse_chat(rendered_prompt, list(referenced_images))
            completion = api_client.chat.completions.create(**params)
            return getattr(completion.choices[0].message, "content", "")


class AsyncPrompty(Prompty):
    """Async prompty is based on Prompty, which is used to invoke prompty in async mode.

    Simple Example:

    .. code-block:: python

        from promptflow.core import class AsyncPrompty
        flow = AsyncPrompty.load(source="path/prompty.prompty")
        result = await flow(input_a=1, input_b=2)

    """

    async def __call__(self, *args, **kwargs) -> Mapping[str, Any]:
        """Calling prompty as a function in async, the inputs should be provided with key word arguments.
        Returns the output of the prompty.
        The function call throws UserErrorException: if the flow is not valid or the inputs are not valid.
        SystemErrorException: if the flow execution failed due to unexpected executor error.

        :param args: positional arguments are not supported.
        :param kwargs: flow inputs with key word arguments.
        :return:
        """
        if args:
            raise UserErrorException("Flow can only be called with keyword arguments.")

        return await super.__call__(**kwargs)
