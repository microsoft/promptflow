# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import os.path
from contextlib import contextmanager
from os import PathLike
from pathlib import Path
from typing import Dict, List, Optional, Union

from promptflow._sdk._constants import DAG_FILE_NAME, SERVICE_FLOW_TYPE_2_CLIENT_FLOW_TYPE, AzureFlowSource, FlowType
from promptflow.azure._ml import AdditionalIncludesMixin, Code

from ..._sdk._utils import PromptflowIgnoreFile, load_yaml
from .._constants._flow import DEFAULT_STORAGE
from .._restclient.flow.models import FlowDto

# pylint: disable=redefined-builtin, unused-argument, f-string-without-interpolation


logger = logging.getLogger(__name__)


class Flow(AdditionalIncludesMixin):
    def __init__(
        self,
        path: Union[str, PathLike],
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
        self.description = description
        self.tags = tags

        if self._flow_source == AzureFlowSource.LOCAL:
            absolute_path = self._validate_flow_from_source(path)
            # flow snapshot folder
            self.code = absolute_path.parent.as_posix()
            self._code_uploaded = False
            self.path = absolute_path.name
            self._flow_dict = self._load_flow_yaml(absolute_path)
            self.name = name or absolute_path.parent.name
            self.description = description or self._flow_dict.get("description", None)
            self.tags = tags or self._flow_dict.get("tags", None)
        elif self._flow_source == AzureFlowSource.AZURE:
            self.flow_id = kwargs.get("flow_id", None)
            self.code = kwargs.get("flow_resource_id", None)
            self.owner = kwargs.get("owner", None)
            self.is_archived = kwargs.get("is_archived", None)
            self.created_date = kwargs.get("created_date", None)

    def _validate_flow_from_source(self, source: Union[str, PathLike]) -> Path:
        """Validate flow from source.

        :param source: The source of the flow.
        :type source: Union[str, PathLike]
        """
        absolute_path = Path(source).resolve().absolute()
        if absolute_path.is_dir():
            absolute_path = absolute_path / DAG_FILE_NAME
        if not absolute_path.exists():
            raise ValueError(f"Flow file {absolute_path.as_posix()} does not exist.")
        return absolute_path

    def _load_flow_yaml(self, path: Union[str, Path]) -> Dict:
        """Load flow yaml file.

        :param path: The path of the flow yaml file.
        :type path: str
        """
        return load_yaml(path)

    # region AdditionalIncludesMixin
    @contextmanager
    def _try_build_local_code(self) -> Optional[Code]:
        """Try to create a Code object pointing to local code and yield it.

        If there is no local code to upload, yield None. Otherwise, yield a Code object pointing to the code.
        """
        with super()._try_build_local_code() as code:
            if isinstance(code, Code):
                # promptflow snapshot has specific ignore logic, like it should ignore `.run` by default
                code._ignore_file = PromptflowIgnoreFile(code.path)
                # promptflow snapshot will always be uploaded to default storage
                code.datastore = DEFAULT_STORAGE
            yield code

    def _get_base_path_for_code(self) -> Path:
        """Get base path for additional includes."""
        # note that self.code is an absolute path, so it is safe to use it as base path
        return Path(self.code)

    def _get_all_additional_includes_configs(self) -> List:
        """Get all additional include configs.
        For flow, its additional include need to be read from dag with a helper function.
        """
        from promptflow._sdk._utils import _get_additional_includes

        return _get_additional_includes(os.path.join(self.code, self.path))

    # endregion

    @classmethod
    def _from_rest_object(cls, rest_object: FlowDto):
        return cls(
            flow_source=AzureFlowSource.AZURE,
            path=rest_object.flow_definition_file_path,
            name=rest_object.flow_name,
            type=SERVICE_FLOW_TYPE_2_CLIENT_FLOW_TYPE[str(rest_object.flow_type).lower()],
            description=rest_object.description,
            tags=rest_object.tags,
            flow_id=rest_object.flow_id,
            flow_resource_id=rest_object.flow_resource_id,
            owner=rest_object.owner.as_dict(),
            is_archived=rest_object.is_archived,
            created_date=rest_object.created_date,
        )

    def _to_dict(self):
        result = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "tags": self.tags,
            "path": self.path,
            "code": str(self.code),
        }
        if self._flow_source == AzureFlowSource.AZURE:
            result["flow_id"] = self.flow_id
            result["owner"] = self.owner
            result["is_archived"] = self.is_archived
            result["created_date"] = str(self.created_date)
        return result
