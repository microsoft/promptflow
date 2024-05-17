# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import copy
import os.path
from contextlib import contextmanager
from os import PathLike
from pathlib import Path
from typing import Dict, List, Optional, Union

import pydash

from promptflow._constants import FlowLanguage
from promptflow._proxy import ProxyFactory
from promptflow._sdk._constants import SERVICE_FLOW_TYPE_2_CLIENT_FLOW_TYPE, AzureFlowSource, FlowType
from promptflow._sdk._utilities.general_utils import PromptflowIgnoreFile, load_yaml, remove_empty_element_from_dict
from promptflow._sdk._utilities.signature_utils import update_signatures
from promptflow._utils.flow_utils import (
    dump_flow_yaml_to_existing_path,
    is_prompty_flow,
    load_flow_dag,
    resolve_flow_path,
)
from promptflow._utils.logger_utils import LoggerFactory
from promptflow.azure._ml import AdditionalIncludesMixin, Code
from promptflow.core._model_configuration import MODEL_CONFIG_NAME_2_CLASS
from promptflow.exceptions import UserErrorException

from .._constants._flow import ADDITIONAL_INCLUDES, DEFAULT_STORAGE, ENVIRONMENT, PYTHON_REQUIREMENTS_TXT
from .._restclient.flow.models import FlowDto

# pylint: disable=redefined-builtin, unused-argument, f-string-without-interpolation

logger = LoggerFactory.get_logger(__name__)


class Flow(AdditionalIncludesMixin):
    DEFAULT_REQUIREMENTS_FILE_NAME = "requirements.txt"

    def __init__(
        self,
        path: Optional[Union[str, PathLike]] = None,
        name: Optional[str] = None,
        type: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        self._flow_source = kwargs.pop("flow_source", AzureFlowSource.LOCAL)
        self.path = path
        self.name = name
        self.type = type or FlowType.STANDARD
        self.display_name = kwargs.get("display_name", None) or name
        self.description = description
        self.tags = tags
        self.owner = kwargs.get("owner", None)
        self.is_archived = kwargs.get("is_archived", None)
        self.created_date = kwargs.get("created_date", None)
        self.flow_portal_url = kwargs.get("flow_portal_url", None)
        # flow's environment, used to calculate session id, value will be set after flow is resolved to code.
        self._environment = {}
        self._is_prompty_flow = is_prompty_flow(path)

        if self._flow_source == AzureFlowSource.LOCAL:
            absolute_path = self._validate_flow_from_source(path)
            # flow snapshot folder
            self.code = absolute_path.parent.as_posix()
            self._code_uploaded = False
            self.path = absolute_path.name
            if self._is_prompty_flow:
                from promptflow.core._flow import Prompty

                self._flow_dict = Prompty.load(source=absolute_path)._data
            else:
                self._flow_dict = self._load_flow_yaml(absolute_path)
            self.display_name = self.display_name or absolute_path.parent.name
            self.description = description or self._flow_dict.get("description", None)
            self.tags = tags or self._flow_dict.get("tags", None)
        elif self._flow_source == AzureFlowSource.PF_SERVICE:
            self.code = kwargs.get("flow_resource_id", None)
        elif self._flow_source == AzureFlowSource.INDEX:
            self.code = kwargs.get("entity_id", None)
        # set this in runtime to validate against signature
        self._init_kwargs = None

    def _validate_flow_from_source(self, source: Union[str, PathLike]) -> Path:
        """Validate flow from source.

        :param source: The source of the flow.
        :type source: Union[str, PathLike]
        """
        flow_path, flow_file = resolve_flow_path(source)
        absolute_path = flow_path / flow_file

        return absolute_path

    def _load_flow_yaml(self, path: Union[str, Path]) -> Dict:
        """Load flow yaml file.

        :param path: The path of the flow yaml file.
        :type path: str
        """
        return load_yaml(path)

    @classmethod
    def _resolve_requirements(cls, flow_path: Union[str, Path], flow_dag: dict):
        """If requirements.txt exists, add it to the flow snapshot. Return True if flow_dag is updated."""

        flow_dir = Path(flow_path)
        if not (flow_dir / cls.DEFAULT_REQUIREMENTS_FILE_NAME).exists():
            return False
        if pydash.get(flow_dag, f"{ENVIRONMENT}.{PYTHON_REQUIREMENTS_TXT}"):
            return False
        logger.debug(
            f"requirements.txt is found in the flow folder: {flow_path.resolve().as_posix()}, "
            "adding it to flow.dag.yaml."
        )
        pydash.set_(flow_dag, f"{ENVIRONMENT}.{PYTHON_REQUIREMENTS_TXT}", cls.DEFAULT_REQUIREMENTS_FILE_NAME)
        return True

    @classmethod
    def _resolve_environment(cls, flow_path: Union[str, Path], flow_dag: dict) -> dict:
        """Resolve flow's environment to dict."""
        environment = {}

        try:
            environment = flow_dag.get("environment", {})
            environment = dict(environment)
            # resolve requirements
            if PYTHON_REQUIREMENTS_TXT in environment:
                req_path = os.path.join(flow_path, environment[PYTHON_REQUIREMENTS_TXT])
                with open(req_path, "r") as f:
                    requirements = f.read().splitlines()
                environment[PYTHON_REQUIREMENTS_TXT] = requirements
        except Exception as e:
            # warn and continue if failed to resolve environment, it should not block the flow upload process.
            logger.warning(f"Failed to resolve environment due to {e}.")

        return environment

    @classmethod
    def _remove_additional_includes(cls, flow_dag: dict):
        """Remove additional includes from flow dag. Return True if removed."""
        if ADDITIONAL_INCLUDES not in flow_dag:
            return False

        logger.debug("Additional includes are found in the flow dag, removing them from flow.dag.yaml after resolved.")
        flow_dag.pop(ADDITIONAL_INCLUDES, None)
        return True

    # region AdditionalIncludesMixin
    @contextmanager
    def _try_build_local_code(self) -> Optional[Code]:
        """Try to create a Code object pointing to local code and yield it.

        If there is no local code to upload, yield None. Otherwise, yield a Code object pointing to the code.
        """
        with super()._try_build_local_code() as code:
            dag_updated = False
            if isinstance(code, Code):
                flow_dir = Path(code.path)
                if self._is_prompty_flow:
                    flow_dag = self._flow_dict
                else:
                    _, flow_dag = load_flow_dag(flow_path=flow_dir)
                original_flow_dag = copy.deepcopy(flow_dag)
                if self._get_all_additional_includes_configs():
                    # Remove additional include in the flow yaml.
                    dag_updated = self._remove_additional_includes(flow_dag)
                # promptflow snapshot has specific ignore logic, like it should ignore `.run` by default
                code._ignore_file = PromptflowIgnoreFile(flow_dir)
                # promptflow snapshot will always be uploaded to default storage
                code.datastore = DEFAULT_STORAGE
                dag_updated = self._resolve_requirements(flow_dir, flow_dag) or dag_updated

                if not self._is_prompty_flow:
                    # generate .promptflow/flow.json for csharp flow as it's required to infer signature for csharp flow
                    flow_directory, flow_file = resolve_flow_path(code.path)
                    ProxyFactory().create_inspector_proxy(self.language).prepare_metadata(
                        flow_file=flow_directory / flow_file, working_dir=flow_directory, init_kwargs=self._init_kwargs
                    )
                dag_updated = update_signatures(code=flow_dir, data=flow_dag) or dag_updated
                # validate init kwargs with signature
                self._validate_init_kwargs(init_signatures=flow_dag.get("init"), init_kwargs=self._init_kwargs)
                # validate and resolve environment
                self._environment = self._resolve_environment(flow_dir, flow_dag)
                if dag_updated and not self._is_prompty_flow:
                    dump_flow_yaml_to_existing_path(flow_dag, flow_dir)
            try:
                yield code
            finally:
                if dag_updated and not self._is_prompty_flow:
                    dump_flow_yaml_to_existing_path(original_flow_dag, flow_dir)

    def _get_base_path_for_code(self) -> Path:
        """Get base path for additional includes."""
        # note that self.code is an absolute path, so it is safe to use it as base path
        return Path(self.code)

    def _get_all_additional_includes_configs(self) -> List:
        """Get all additional include configs.
        For flow, its additional include need to be read from dag with a helper function.
        """
        from promptflow._sdk._utilities.general_utils import _get_additional_includes

        return _get_additional_includes(os.path.join(self.code, self.path))

    # endregion

    @classmethod
    def _from_pf_service(cls, rest_object: FlowDto):
        return cls(
            flow_source=AzureFlowSource.PF_SERVICE,
            path=rest_object.flow_definition_file_path,
            name=rest_object.flow_id,
            type=SERVICE_FLOW_TYPE_2_CLIENT_FLOW_TYPE[str(rest_object.flow_type).lower()],
            description=rest_object.description,
            tags=rest_object.tags,
            display_name=rest_object.flow_name,
            flow_resource_id=rest_object.flow_resource_id,
            owner=rest_object.owner.as_dict(),
            is_archived=rest_object.is_archived,
            created_date=rest_object.created_date,
            flow_portal_url=rest_object.studio_portal_endpoint,
        )

    @classmethod
    def _from_index_service(cls, rest_object: Dict):
        properties = rest_object["properties"]
        annotations = rest_object["annotations"]

        flow_type = properties.get("flowType", None).lower()
        # rag type flow is shown as standard flow in UX, not sure why this type exists in service code
        if flow_type == "rag":
            flow_type = FlowType.STANDARD
        elif flow_type:
            flow_type = SERVICE_FLOW_TYPE_2_CLIENT_FLOW_TYPE[flow_type]

        return cls(
            flow_source=AzureFlowSource.INDEX,
            path=properties.get("flowDefinitionFilePath", None),
            name=properties.get("flowId", None),
            display_name=annotations.get("flowName", None),
            type=flow_type,
            description=annotations.get("description", None),
            tags=annotations.get("tags", None),
            entity_id=rest_object["entityId"],
            owner=annotations.get("owner", None),
            is_archived=annotations.get("isArchived", None),
            created_date=annotations.get("createdDate", None),
        )

    def _to_dict(self):
        result = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "tags": self.tags,
            "path": self.path,
            "code": str(self.code),
            "display_name": self.display_name,
            "owner": self.owner,
            "is_archived": self.is_archived,
            "created_date": str(self.created_date),
            "flow_portal_url": self.flow_portal_url,
        }
        return remove_empty_element_from_dict(result)

    @property
    def language(self):
        return self._flow_dict.get("language", FlowLanguage.Python)

    @classmethod
    def _validate_init_kwargs(cls, init_signatures: dict, init_kwargs: dict):
        init_kwargs = init_kwargs or {}
        if not isinstance(init_kwargs, dict):
            raise UserErrorException(f"Init kwargs should be a dict, got {type(init_kwargs)}")
        # validate init kwargs against signature
        for param_name, param_value in init_kwargs.items():
            if param_name not in init_signatures:
                raise UserErrorException(
                    f"Init kwargs {param_name} is not in the flow signature. Current signatures: {init_signatures}"
                )
            param_signature = init_signatures[param_name]
            param_type = param_signature.get("type")
            if param_type in MODEL_CONFIG_NAME_2_CLASS:
                if pydash.get(param_value, "connection") is None:
                    raise UserErrorException(
                        f"Init kwargs {param_name} with type {param_type} is missing connection. "
                        "Only connection model configs with connection is supported in cloud."
                    )
