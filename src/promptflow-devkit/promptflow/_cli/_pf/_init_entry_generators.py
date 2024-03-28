# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import inspect
import json
import shutil
from abc import ABC, abstractmethod
from ast import literal_eval
from enum import Enum
from pathlib import Path

from jinja2 import Environment, Template, meta

from promptflow._sdk._constants import DEFAULT_ENCODING
from promptflow._utils.flow_utils import is_executable_chat_flow
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.exceptions import UserErrorException

logger = get_cli_sdk_logger()
TEMPLATE_PATH = Path(__file__).parent.parent / "data" / "entry_flow"
CHAT_FLOW_TEMPLATE_PATH = Path(__file__).parent.parent / "data" / "chat_flow" / "template"
TOOL_TEMPLATE_PATH = Path(__file__).parent.parent / "data" / "package_tool"
EXTRA_FILES_MAPPING = {"requirements.txt": "requirements_txt", ".gitignore": "gitignore"}
SERVE_TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "_sdk" / "data" / "executable"


class BaseGenerator(ABC):
    @property
    @abstractmethod
    def tpl_file(self):
        pass

    @property
    @abstractmethod
    def entry_template_keys(self):
        pass

    def generate(self) -> str:
        """Generate content based on given template and actual value of template keys."""
        with open(self.tpl_file, encoding=DEFAULT_ENCODING) as f:
            entry_template = f.read()
            entry_template = Template(entry_template, trim_blocks=True, lstrip_blocks=True)

        return entry_template.render(**{key: getattr(self, key) for key in self.entry_template_keys})

    def generate_to_file(self, target):
        """Generate content to a file based on given template and actual value of template keys."""
        target = Path(target).resolve()
        action = "Overwriting" if target.exists() else "Creating"
        print(f"{action} {target.resolve()}...")
        with open(target, "w", encoding=DEFAULT_ENCODING) as f:
            f.write(self.generate())


class ToolPyGenerator(BaseGenerator):
    def __init__(self, entry, function, function_obj):
        self.function_import = f"from {Path(entry).stem} import {function}"
        self.entry_function = function
        self.tool_function = f"{function}_tool"
        # TODO: support default for tool args
        self.tool_arg_list = inspect.signature(function_obj).parameters.values()

    @property
    def tpl_file(self):
        return TEMPLATE_PATH / "tool.py.jinja2"

    @property
    def entry_template_keys(self):
        return ["function_import", "entry_function", "tool_function", "tool_arg_list"]


class ValueType(str, Enum):
    INT = "int"
    DOUBLE = "double"
    BOOL = "bool"
    STRING = "string"
    LIST = "list"
    OBJECT = "object"

    @staticmethod
    def from_type(t: type):
        if t == int:
            return ValueType.INT
        if t == float:
            return ValueType.DOUBLE
        if t == bool:
            return ValueType.BOOL
        if t == str:
            return ValueType.STRING
        if t == list:
            return ValueType.LIST
        return ValueType.OBJECT


class ToolMetaGenerator(BaseGenerator):
    def __init__(self, tool_py, function, function_obj, prompt_params):
        self.tool_file = tool_py
        self.tool_function = f"{function}_tool"
        # TODO: support default for tool meta args
        self.tool_meta_args = self.get_tool_meta_args(function_obj)
        self._prompt_params = prompt_params

    @property
    def prompt_params(self):
        from promptflow._core.tool_meta_generator import generate_prompt_meta_dict

        prompt_objs = {}
        for key, file_name in self._prompt_params.items():
            file_path = Path(file_name)
            if not file_path.exists():
                logger.warning(
                    f'Cannot find the prompt template "{file_name}", creating an empty prompt file in the flow...'
                )
                with open(file_path, "w") as f:
                    f.write("{# please enter your prompt content in this file. #}")

            with open(file_name, "r") as f:
                content = f.read()
            name = Path(file_name).stem
            prompt_objs[key] = generate_prompt_meta_dict(name, content, prompt_only=True, source=file_name)
        return prompt_objs

    def get_tool_meta_args(self, function_obj):
        func_params = inspect.signature(function_obj).parameters
        # TODO: Support enum/union in the future
        return {k: ValueType.from_type(v.annotation).value for k, v in func_params.items()}

    @property
    def tpl_file(self):
        return TEMPLATE_PATH / "flow.tools.json.jinja2"

    @property
    def entry_template_keys(self):
        return ["prompt_params", "tool_file", "tool_meta_args", "tool_function"]


class FlowDAGGenerator(BaseGenerator):
    def __init__(self, tool_py, function, function_obj, prompt_params):
        self.tool_file = tool_py
        self.main_node_name = function
        self.prompt_params = prompt_params
        self.setup_sh = None
        self.python_requirements_txt = None
        self._prompt_inputs = None
        self._func_params = None
        self._function_obj = function_obj
        # Abstract prompt param from tool meta args
        self.flow_inputs = self.get_flow_inputs(prompt_params)

    def get_flow_inputs(self, prompt_params):
        """Generate the flow inputs"""
        flow_inputs = {
            k: ValueType.from_type(v.annotation).value for k, v in self.func_params.items() if k not in prompt_params
        }
        for prompt_inputs in self.prompt_inputs.values():
            flow_inputs.update(prompt_inputs)
        return flow_inputs

    @property
    def tpl_file(self):
        return TEMPLATE_PATH / "flow.dag.yaml.jinja2"

    @property
    def func_params(self):
        """Generate function inputs without prompt templates."""
        if self._func_params is None:
            self._func_params = {
                k: v for k, v in inspect.signature(self._function_obj).parameters.items() if k not in self.prompt_params
            }
        return self._func_params

    @property
    def prompt_inputs(self):
        """Generate prompt inputs."""
        if self._prompt_inputs is None:
            self._prompt_inputs = {}
            for prompt_name, file_name in self.prompt_params.items():
                try:
                    with open(file_name, "r") as f:
                        env = Environment()
                        ast = env.parse(f.read())
                        variables = meta.find_undeclared_variables(ast)
                        self._prompt_inputs[prompt_name] = {item: "string" for item in variables or []}
                except Exception as e:
                    logger.warning(f"Get the prompt input from {file_name} failed, {e}.")
        return self._prompt_inputs

    @property
    def entry_template_keys(self):
        return [
            "flow_inputs",
            "main_node_name",
            "prompt_params",
            "tool_file",
            "setup_sh",
            "python_requirements_txt",
            "prompt_inputs",
            "func_params",
        ]

    def generate_to_file(self, target):
        # Get requirements.txt and setup.sh from target folder.
        requirements_file = "requirements.txt"
        if (Path(target).parent / requirements_file).exists():
            self.python_requirements_txt = requirements_file
        setup_file = "setup.sh"
        if (Path(target).parent / setup_file).exists():
            self.setup_sh = setup_file
        super().generate_to_file(target=target)


class FlowMetaYamlGenerator(BaseGenerator):
    def __init__(self, flow_name):
        self.flow_name = flow_name

    @property
    def tpl_file(self):
        return TEMPLATE_PATH / "flow.meta.yaml.jinja2"

    @property
    def entry_template_keys(self):
        return ["flow_name"]


class StreamlitFileReplicator:
    def __init__(self, flow_name, flow_dag_path):
        self.flow_name = flow_name
        self.flow_dag_path = Path(flow_dag_path)
        self.executable = ExecutableFlow.from_yaml(
            flow_file=Path(self.flow_dag_path.name), working_dir=self.flow_dag_path.parent
        )
        self.is_chat_flow, self.chat_history_input_name, error_msg = is_executable_chat_flow(self.executable)

    @property
    def flow_inputs(self):
        if self.is_chat_flow:
            results = {}
            for flow_input, value in self.executable.inputs.items():
                if not value.is_chat_history:
                    if value.type.value not in [ValueType.STRING.value, ValueType.LIST.value]:
                        raise UserErrorException(
                            f"Only support string or list type for chat flow input, but got {value.type.value}."
                        )
                    results.update({flow_input: (value.default, value.type.value)})
        else:
            results = {
                flow_input: (value.default, value.type.value) for flow_input, value in self.executable.inputs.items()
            }
        return results

    @property
    def label(self):
        return "Chat" if self.is_chat_flow else "Run"

    @property
    def py_file(self):
        return SERVE_TEMPLATE_PATH / "main.py"

    @property
    def flow_path(self):
        return self.flow_dag_path.as_posix()

    @property
    def chat_output_name(self):
        try:
            output_name = next(
                filter(
                    lambda key: self.executable.outputs[key].is_chat_output,
                    self.executable.outputs.keys(),
                )
            )
        except StopIteration:
            output_name = None
        return output_name

    @property
    def is_streaming(self):
        return True if self.is_chat_flow else False

    @property
    def entry_template_keys(self):
        return [
            "flow_name",
            "flow_path",
            "is_chat_flow",
            "chat_history_input_name",
            "flow_inputs",
            "label",
            "chat_output_name",
            "is_streaming",
        ]

    def generate_to_file(self, target):
        if Path(target).name == "main.py":
            target = Path(target).resolve()
            shutil.copy(self.py_file, target)
            config_content = {key: getattr(self, key) for key in self.entry_template_keys}
            with open(target.parent / "config.json", "w") as file:
                json.dump(config_content, file, indent=4)
        else:
            shutil.copy(SERVE_TEMPLATE_PATH / Path(target).name, target)


class ChatFlowDAGGenerator(BaseGenerator):
    def __init__(self, connection, deployment):
        self.connection = connection
        self.deployment = deployment

    @property
    def tpl_file(self):
        return CHAT_FLOW_TEMPLATE_PATH / "flow.dag.yaml.jinja2"

    @property
    def entry_template_keys(self):
        return ["connection", "deployment"]


class AzureOpenAIConnectionGenerator(BaseGenerator):
    def __init__(self, connection):
        self.connection = connection

    @property
    def tpl_file(self):
        return CHAT_FLOW_TEMPLATE_PATH / "azure_openai.yaml.jinja2"

    @property
    def entry_template_keys(self):
        return ["connection"]


class OpenAIConnectionGenerator(BaseGenerator):
    def __init__(self, connection):
        self.connection = connection

    @property
    def tpl_file(self):
        return CHAT_FLOW_TEMPLATE_PATH / "openai.yaml.jinja2"

    @property
    def entry_template_keys(self):
        return ["connection"]


def copy_extra_files(flow_path, extra_files, overwrite=False):
    for file_name in extra_files:
        extra_file_path = (
            Path(__file__).parent.parent / "data" / "entry_flow" / EXTRA_FILES_MAPPING.get(file_name, file_name)
        )
        target_path = Path(flow_path) / file_name
        if target_path.exists() and not overwrite:
            continue
        action = "Overwriting" if target_path.exists() else "Creating"
        print(f"{action} {target_path.resolve()}...")
        shutil.copy2(extra_file_path, target_path)


class ToolPackageGenerator(BaseGenerator):
    def __init__(self, tool_name, icon=None, extra_info=None):
        self.tool_name = tool_name
        self._extra_info = extra_info
        self.icon = icon

    @property
    def extra_info(self):
        if self._extra_info:
            extra_info = {}
            for k, v in self._extra_info.items():
                try:
                    extra_info[k] = literal_eval(v)
                except Exception:
                    extra_info[k] = repr(v)
            return extra_info
        else:
            return {}

    @property
    def tpl_file(self):
        return TOOL_TEMPLATE_PATH / "tool.py.jinja2"

    @property
    def entry_template_keys(self):
        return ["tool_name", "extra_info", "icon"]


class SetupGenerator(BaseGenerator):
    def __init__(self, package_name, tool_name):
        self.package_name = package_name
        self.tool_name = tool_name

    @property
    def tpl_file(self):
        return TOOL_TEMPLATE_PATH / "setup.py.jinja2"

    @property
    def entry_template_keys(self):
        return ["package_name", "tool_name"]


class ToolPackageUtilsGenerator(BaseGenerator):
    def __init__(self, package_name):
        self.package_name = package_name

    @property
    def tpl_file(self):
        return TOOL_TEMPLATE_PATH / "utils.py.jinja2"

    @property
    def entry_template_keys(self):
        return ["package_name"]


class ToolReadmeGenerator(BaseGenerator):
    def __init__(self, package_name, tool_name):
        self.package_name = package_name
        self.tool_name = tool_name

    @property
    def tpl_file(self):
        return TOOL_TEMPLATE_PATH / "README.md.jinja2"

    @property
    def entry_template_keys(self):
        return ["package_name", "tool_name"]


class InitGenerator(BaseGenerator):
    @property
    def tpl_file(self):
        return TOOL_TEMPLATE_PATH / "init.py"

    @property
    def entry_template_keys(self):
        pass

    def generate(self) -> str:
        with open(self.tpl_file) as f:
            init_content = f.read()
        return init_content
