# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import inspect
import logging
import shutil
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from jinja2 import Environment, Template, meta

from promptflow._sdk._constants import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "data" / "entry_flow"
EXTRA_FILES_MAPPING = {"requirements.txt": "requirements_txt", ".gitignore": "gitignore"}
SERVE_TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "sdk" / "data" / "executable"


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
        with open(self.tpl_file) as f:
            entry_template = f.read()
            entry_template = Template(entry_template, trim_blocks=True, lstrip_blocks=True)

        return entry_template.render(**{key: getattr(self, key) for key in self.entry_template_keys})

    def generate_to_file(self, target):
        """Generate content to a file based on given template and actual value of template keys."""
        target = Path(target).resolve()
        action = "Overwriting" if target.exists() else "Creating"
        print(f"{action} {target.resolve()}...")
        with open(target, "w", encoding="utf-8") as f:
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


class StreamlitFileGenerator(BaseGenerator):
    def __init__(self, flow_name, flow_dag_path):
        self.flow_name = flow_name
        self.flow_dag_path = Path(flow_dag_path)

    @property
    def flow_inputs(self):
        from promptflow.contracts.flow import Flow as ExecutableFlow
        executable = ExecutableFlow.from_yaml(flow_file=Path(self.flow_dag_path.name),
                                              working_dir=self.flow_dag_path.parent)
        return {flow_input: (value.default, True if isinstance(value.type, list) else False)
                for flow_input, value in executable.inputs.items()}

    @property
    def flow_inputs_params(self):
        flow_inputs_params = ["=".join([flow_input, flow_input]) for flow_input, _ in self.flow_inputs.items()]
        return ",".join(flow_inputs_params)

    @property
    def tpl_file(self):
        return TEMPLATE_PATH / "main.py.jinja2"

    @property
    def entry_template_keys(self):
        return ["flow_name", "flow_inputs", "flow_inputs_params"]


def copy_extra_files(flow_path, extra_files):
    for file_name in extra_files:
        extra_file_path = (
            Path(__file__).parent.parent / "data" / "entry_flow" / EXTRA_FILES_MAPPING.get(file_name, file_name)
        )
        target_path = Path(flow_path) / file_name
        action = "Overwriting" if target_path.exists() else "Creating"
        print(f"{action} {target_path.resolve()}...")
        shutil.copy2(extra_file_path, target_path)
