# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import json
import typing
from dataclasses import dataclass
from pathlib import Path

from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR, AzureMLWorkspaceTriad
from promptflow._sdk._utils import json_load
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.core._errors import MissingRequiredPackage

_logger = get_cli_sdk_logger()


@dataclass
class WorkspaceKindLocalCache:
    subscription_id: str
    resource_group_name: str
    workspace_name: str
    kind: typing.Optional[str] = None
    timestamp: typing.Optional[datetime.datetime] = None

    SUBSCRIPTION_ID = "subscription_id"
    RESOURCE_GROUP_NAME = "resource_group_name"
    WORKSPACE_NAME = "workspace_name"
    KIND = "kind"
    TIMESTAMP = "timestamp"
    # class-related constants
    PF_DIR_TRACING = "tracing"
    WORKSPACE_KIND_LOCAL_CACHE_EXPIRE_DAYS = 1

    def __post_init__(self):
        if self.is_cache_exists:
            cache = json_load(self.cache_path)
            self.kind = cache[self.KIND]
            self.timestamp = datetime.datetime.fromisoformat(cache[self.TIMESTAMP])

    @property
    def cache_path(self) -> Path:
        tracing_dir = HOME_PROMPT_FLOW_DIR / self.PF_DIR_TRACING
        if not tracing_dir.exists():
            tracing_dir.mkdir(parents=True)
        filename = f"{self.subscription_id}_{self.resource_group_name}_{self.workspace_name}.json"
        return (tracing_dir / filename).resolve()

    @property
    def is_cache_exists(self) -> bool:
        return self.cache_path.is_file()

    @property
    def is_expired(self) -> bool:
        if not self.is_cache_exists:
            return True
        time_delta = datetime.datetime.now() - self.timestamp
        return time_delta.days > self.WORKSPACE_KIND_LOCAL_CACHE_EXPIRE_DAYS

    def get_kind(self) -> str:
        if not self.is_cache_exists or self.is_expired:
            _logger.debug(f"refreshing local cache for resource {self.workspace_name}...")
            self._refresh()
        _logger.debug(f"local cache kind for resource {self.workspace_name}: {self.kind}")
        return self.kind

    def _refresh(self) -> None:
        self.kind = self._get_workspace_kind_from_azure()
        self.timestamp = datetime.datetime.now()
        cache = {
            self.SUBSCRIPTION_ID: self.subscription_id,
            self.RESOURCE_GROUP_NAME: self.resource_group_name,
            self.WORKSPACE_NAME: self.workspace_name,
            self.KIND: self.kind,
            self.TIMESTAMP: self.timestamp.isoformat(),
        }
        with open(self.cache_path, "w") as f:
            f.write(json.dumps(cache))

    def _get_workspace_kind_from_azure(self) -> str:
        try:
            from azure.ai.ml import MLClient

            from promptflow.azure._cli._utils import get_credentials_for_cli
        except ImportError:
            error_message = "Please install 'promptflow-azure' to use Azure related tracing features."
            raise MissingRequiredPackage(message=error_message)

        _logger.debug("trying to get workspace from Azure...")
        ml_client = MLClient(
            credential=get_credentials_for_cli(),
            subscription_id=self.subscription_id,
            resource_group_name=self.resource_group_name,
            workspace_name=self.workspace_name,
        )
        ws = ml_client.workspaces.get(name=self.workspace_name)
        return ws._kind


def get_workspace_kind(ws_triad: AzureMLWorkspaceTriad) -> str:
    """Get workspace kind.

    Note that we will cache this result locally with timestamp, so that we don't
    really need to request every time, but need to check timestamp.
    """
    return WorkspaceKindLocalCache(
        subscription_id=ws_triad.subscription_id,
        resource_group_name=ws_triad.resource_group_name,
        workspace_name=ws_triad.workspace_name,
    ).get_kind()
