# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import copy
import datetime
import json
import shutil
import uuid
from os import PathLike
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from marshmallow import Schema

from promptflow._sdk._constants import (
    BASE_PATH_CONTEXT_KEY,
    HOME_PROMPT_FLOW_DIR,
    PARAMS_OVERRIDE_KEY,
    PROMPT_FLOW_EXP_DIR_NAME,
    ExperimentNodeType,
    ExperimentStatus,
)
from promptflow._sdk._errors import ExperimentValidationError, ExperimentValueError
from promptflow._sdk._orm.experiment import Experiment as ORMExperiment
from promptflow._sdk._utilities.general_utils import (
    _merge_local_code_and_additional_includes,
    _sanitize_python_variable_name,
)
from promptflow._sdk.entities import Run
from promptflow._sdk.entities._validation import MutableValidationResult, SchemaValidatableMixin
from promptflow._sdk.entities._yaml_translatable import YAMLTranslatableMixin
from promptflow._sdk.schemas._experiment import (
    ChatGroupSchema,
    CommandNodeSchema,
    ExperimentDataSchema,
    ExperimentInputSchema,
    ExperimentSchema,
    ExperimentTemplateSchema,
    FlowNodeSchema,
)
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.contracts.tool import ValueType

logger = get_cli_sdk_logger()


class ExperimentData(YAMLTranslatableMixin):
    def __init__(self, name, path, **kwargs):
        self.name = name
        self.path = path

    @classmethod
    def _get_schema_cls(cls):
        return ExperimentDataSchema


class ExperimentInput(YAMLTranslatableMixin):
    def __init__(self, name, default, type, **kwargs):
        self.name = name
        self.type, self.default = self._resolve_type_and_default(type, default)

    @classmethod
    def _get_schema_cls(cls):
        return ExperimentInputSchema

    def _resolve_type_and_default(self, typ, default):
        supported_types = [
            ValueType.INT,
            ValueType.STRING,
            ValueType.DOUBLE,
            ValueType.LIST,
            ValueType.OBJECT,
            ValueType.BOOL,
        ]
        value_type: ValueType = next((i for i in supported_types if typ.lower() == i.value.lower()), None)
        if value_type is None:
            raise ExperimentValueError(f"Unknown experiment input type {typ!r}, supported are {supported_types}.")
        return value_type.value, value_type.parse(default) if default is not None else None

    @classmethod
    def _load_from_dict(cls, data: Dict, context: Dict, additional_message: str = None, **kwargs):
        # Override this to avoid 'type' got pop out
        schema_cls = cls._get_schema_cls()
        try:
            loaded_data = schema_cls(context=context).load(data, **kwargs)
        except Exception as e:
            raise Exception(f"Load experiment input failed with {str(e)}. f{(additional_message or '')}.")
        return cls(base_path=context[BASE_PATH_CONTEXT_KEY], **loaded_data)


class FlowNode(YAMLTranslatableMixin):
    def __init__(
        self,
        path: Union[Path, str],
        name: str,
        # input fields are optional since it's not stored in DB
        data: Optional[str] = None,
        variant: Optional[str] = None,
        run: Optional[Union["Run", str]] = None,
        inputs: Optional[dict] = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[Dict[str, str]]] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        connections: Optional[Dict[str, Dict]] = None,
        properties: Optional[Dict[str, Any]] = None,
        init: Optional[dict] = None,
        **kwargs,
    ):
        self.type = ExperimentNodeType.FLOW
        self.data = data
        self.inputs = inputs or {}
        self.display_name = display_name
        self.description = description
        self.tags = tags
        self.variant = variant
        self.run = run
        self.environment_variables = environment_variables or {}
        self.connections = connections or {}
        self._properties = properties or {}
        # init here to make sure those fields initialized in all branches.
        self.path = path
        # default run name: flow directory name + timestamp
        self.name = name
        self.init = init or {}
        self._runtime = kwargs.get("runtime", None)
        self._resources = kwargs.get("resources", None)

    @classmethod
    def _get_schema_cls(cls):
        return FlowNodeSchema

    def _save_snapshot(self, target):
        """Save flow source to experiment snapshot."""
        # Resolve additional includes in flow
        from promptflow._sdk.entities._flows import Prompty

        from .._load_functions import load_flow
        from .._orchestrator import remove_additional_includes

        Path(target).mkdir(parents=True, exist_ok=True)
        flow = load_flow(source=self.path)
        saved_flow_path = Path(target) / self.name
        if isinstance(flow, Prompty):
            shutil.copytree(src=flow.code, dst=saved_flow_path)
            saved_flow_path = saved_flow_path / Path(self.path).name
        else:
            with _merge_local_code_and_additional_includes(code_path=flow.code) as resolved_flow_dir:
                remove_additional_includes(Path(resolved_flow_dir))
                shutil.copytree(src=resolved_flow_dir, dst=saved_flow_path)
        logger.debug(f"Flow source saved to {saved_flow_path}.")
        self.path = saved_flow_path.resolve().absolute().as_posix()


class CommandNode(YAMLTranslatableMixin):
    def __init__(
        self,
        command,
        name,
        inputs=None,
        outputs=None,
        runtime=None,
        environment_variables=None,
        code=None,
        display_name=None,
        resources=None,
        identity=None,
        **kwargs,
    ):
        self.type = ExperimentNodeType.COMMAND
        self.name = name
        self.display_name = display_name
        self.code = code
        self.command = command
        self.inputs = inputs or {}
        self.outputs = outputs or {}
        self.runtime = runtime
        self.resources = resources
        self.identity = identity
        self.environment_variables = environment_variables or {}

    @classmethod
    def _get_schema_cls(cls):
        return CommandNodeSchema

    def _save_snapshot(self, target):
        """Save command source to experiment snapshot."""
        Path(target).mkdir(parents=True, exist_ok=True)
        saved_path = Path(target) / self.name
        if not self.code:
            # Create an empty folder
            saved_path.mkdir(parents=True, exist_ok=True)
            self.code = saved_path.resolve().absolute().as_posix()
            return
        code = Path(self.code)
        if not code.exists():
            raise ExperimentValueError(f"Command node code {code} does not exist.")
        if code.is_dir():
            shutil.copytree(src=self.code, dst=saved_path)
        else:
            saved_path.mkdir(parents=True, exist_ok=True)
            shutil.copy(src=self.code, dst=saved_path)
        logger.debug(f"Command node source saved to {saved_path}.")
        self.code = saved_path.resolve().absolute().as_posix()


class ChatGroupNode(YAMLTranslatableMixin):
    def __init__(
        self,
        name,
        roles: List[Dict[str, Any]],
        max_turns: Optional[int] = None,
        max_tokens: Optional[int] = None,
        max_time: Optional[int] = None,
        stop_signal: Optional[str] = None,
        code: Union[Path, str] = None,
        **kwargs,
    ):
        self.type = ExperimentNodeType.CHAT_GROUP
        self.name = name
        self.roles = roles
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.max_time = max_time
        self.stop_signal = stop_signal
        self.code = code

    @classmethod
    def _get_schema_cls(cls):
        return ChatGroupSchema

    def _save_snapshot(self, target):
        """Save chat group source to experiment snapshot."""
        target = Path(target).resolve()
        logger.debug(f"Saving chat group node {self.name!r} snapshot to {target.as_posix()!r}.")
        saved_path = target / self.name
        saved_path.mkdir(parents=True, exist_ok=True)

        for role in self.roles:
            role_path = Path(role["path"]).resolve()
            if not role_path.exists():
                raise ExperimentValueError(f"Chat role path {role_path.as_posix()!r} does not exist.")

            if role_path.is_dir():
                shutil.copytree(src=role_path, dst=saved_path / role["role"])
            else:
                shutil.copytree(src=role_path.parent, dst=saved_path / role["role"])

        self.code = saved_path.resolve().as_posix()


class ExperimentTemplate(YAMLTranslatableMixin, SchemaValidatableMixin):
    def __init__(self, nodes, description=None, data=None, inputs=None, **kwargs):
        self._base_path = kwargs.get(BASE_PATH_CONTEXT_KEY, Path("."))
        self.dir_name = self._get_directory_name()
        self.description = description
        self.nodes = nodes
        self.data = data or []
        self.inputs = inputs or []
        self._source_path = None

    @classmethod
    # pylint: disable=unused-argument
    def _resolve_cls_and_type(cls, **kwargs):
        return cls, "experiment_template"

    @classmethod
    def _get_schema_cls(cls):
        return ExperimentTemplateSchema

    @classmethod
    def _load(
        cls,
        data: Optional[Dict] = None,
        yaml_path: Optional[Union[PathLike, str]] = None,
        params_override: Optional[list] = None,
        **kwargs,
    ):
        data = data or {}
        params_override = params_override or []
        context = {
            BASE_PATH_CONTEXT_KEY: Path(yaml_path).parent if yaml_path else Path("./"),
            PARAMS_OVERRIDE_KEY: params_override,
        }
        logger.debug(f"Loading class object with data {data}, params_override {params_override}, context {context}.")
        exp = cls._load_from_dict(
            data=data,
            context=context,
            additional_message="Failed to load experiment",
            **kwargs,
        )
        if yaml_path:
            exp._source_path = yaml_path
        return exp

    def _get_directory_name(self) -> str:
        """Get experiment template directory name."""
        try:
            folder_name = Path(self._base_path).resolve().absolute().name
            return folder_name
        except Exception as e:
            logger.debug(f"Failed to generate template name, error: {e}, use uuid.")
            return str(uuid.uuid4())

    @classmethod
    def _load_from_dict(cls, data: Dict, context: Dict, additional_message: str = None, **kwargs):
        schema_cls = cls._get_schema_cls()
        try:
            loaded_data = schema_cls(context=context).load(data, **kwargs)
        except Exception as e:
            raise Exception(f"Load experiment template failed with {str(e)}. f{(additional_message or '')}.")
        return cls(base_path=context[BASE_PATH_CONTEXT_KEY], **loaded_data)

    @classmethod
    def _create_schema_for_validation(cls, context) -> Schema:
        return cls._get_schema_cls()(context=context)

    def _default_context(self) -> dict:
        return {BASE_PATH_CONTEXT_KEY: self._base_path}

    @classmethod
    def _create_validation_error(cls, message: str, no_personal_data_message: str) -> Exception:
        return ExperimentValidationError(
            message=message,
            no_personal_data_message=no_personal_data_message,
        )

    def _customized_validate(self) -> MutableValidationResult:
        """Validate the resource with customized logic.

        Override this method to add customized validation logic.

        :return: The customized validation result
        :rtype: MutableValidationResult
        """
        pass


class Experiment(ExperimentTemplate):
    def __init__(
        self,
        nodes,
        name=None,
        data=None,
        inputs=None,
        status=ExperimentStatus.NOT_STARTED,
        node_runs=None,
        properties=None,
        **kwargs,
    ):
        self.name = name or self._generate_name()
        self.status = status
        self.node_runs = node_runs or {}
        self.properties = properties or {}
        self.created_on = kwargs.get("created_on", datetime.datetime.now().isoformat())
        self.last_start_time = kwargs.get("last_start_time", None)
        self.last_end_time = kwargs.get("last_end_time", None)
        self.is_archived = kwargs.get("is_archived", False)
        self._output_dir = HOME_PROMPT_FLOW_DIR / PROMPT_FLOW_EXP_DIR_NAME / self.name
        super().__init__(nodes, name=self.name, data=data, inputs=inputs, **kwargs)

    @classmethod
    def _get_schema_cls(cls):
        return ExperimentSchema

    @classmethod
    # pylint: disable=unused-argument
    def _resolve_cls_and_type(cls, **kwargs):
        return cls, "experiment"

    def _generate_name(self) -> str:
        """Generate a experiment name."""
        try:
            folder_name = Path(self._base_path).resolve().absolute().name
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            exp_name = f"{folder_name}_{timestamp}"
            return _sanitize_python_variable_name(exp_name)
        except Exception as e:
            logger.debug(f"Failed to generate experiment name, error: {e}, use uuid.")
            return str(uuid.uuid4())

    def _save_snapshot_and_update_node(
        self,
    ):
        """Save node source to experiment snapshot, update node path."""
        snapshot_dir = self._output_dir / "snapshots"
        for node in self.nodes:
            node._save_snapshot(snapshot_dir)

    def _append_node_run(self, node_name, run: Run):
        """Append node run to experiment."""
        if node_name not in self.node_runs or not isinstance(self.node_runs[node_name], list):
            self.node_runs[node_name] = []
        # TODO: Review this
        self.node_runs[node_name].append({"name": run.name, "status": run.status})

    def _to_orm_object(self):
        """Convert to ORM object."""
        result = ORMExperiment(
            name=self.name,
            description=self.description,
            status=self.status,
            created_on=self.created_on,
            archived=self.is_archived,
            last_start_time=self.last_start_time,
            last_end_time=self.last_end_time,
            properties=json.dumps(self.properties),
            data=json.dumps([item._to_dict() for item in self.data]),
            inputs=json.dumps([input._to_dict() for input in self.inputs]),
            nodes=json.dumps([node._to_dict() for node in self.nodes]),
            node_runs=json.dumps(self.node_runs),
        )
        logger.debug(f"Experiment to ORM object: {result.__dict__}")
        return result

    @classmethod
    def _from_orm_object(cls, obj: ORMExperiment) -> "Experiment":
        """Create a experiment object from ORM object."""
        nodes = []
        context = {BASE_PATH_CONTEXT_KEY: "./"}
        for node_dict in json.loads(obj.nodes):
            if node_dict["type"] == ExperimentNodeType.FLOW:
                nodes.append(
                    FlowNode._load_from_dict(node_dict, context=context, additional_message="Failed to load node.")
                )
            elif node_dict["type"] == ExperimentNodeType.COMMAND:
                nodes.append(
                    CommandNode._load_from_dict(node_dict, context=context, additional_message="Failed to load node.")
                )
            elif node_dict["type"] == ExperimentNodeType.CHAT_GROUP:
                nodes.append(
                    ChatGroupNode._load_from_dict(node_dict, context=context, additional_message="Failed to load node.")
                )
            else:
                raise Exception(f"Unknown node type {node_dict['type']}")
        data = [
            ExperimentData._load_from_dict(item, context=context, additional_message="Failed to load experiment data")
            for item in json.loads(obj.data)
        ]
        inputs = [
            ExperimentInput._load_from_dict(
                item, context=context, additional_message="Failed to load experiment inputs"
            )
            for item in json.loads(obj.inputs)
        ]

        return cls(
            name=obj.name,
            description=obj.description,
            status=obj.status,
            created_on=obj.created_on,
            last_start_time=obj.last_start_time,
            last_end_time=obj.last_end_time,
            is_archived=obj.archived,
            properties=json.loads(obj.properties),
            data=data,
            inputs=inputs,
            nodes=nodes,
            node_runs=json.loads(obj.node_runs),
        )

    @classmethod
    def from_template(cls, template: ExperimentTemplate, name=None):
        """Create a experiment object from template."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        exp_name = name or f"{template.dir_name}_{timestamp}"
        experiment = cls(
            name=exp_name,
            description=template.description,
            data=copy.deepcopy(template.data),
            inputs=copy.deepcopy(template.inputs),
            nodes=copy.deepcopy(template.nodes),
            base_path=template._base_path,
        )
        logger.debug("Start saving snapshot and update node.")
        experiment._save_snapshot_and_update_node()
        return experiment
