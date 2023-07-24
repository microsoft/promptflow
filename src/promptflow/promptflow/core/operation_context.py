from contextvars import ContextVar

from promptflow._version import VERSION
from promptflow.core.flow_execution_context import FlowExecutionContext
from promptflow.utils.utils import get_runtime_version
from typing import Dict


class OperationContext:

    _instance = None

    def __init__(self):
        self.deploy_config = None
        self.user_agent = None
        self.runtime_version = get_runtime_version()
        self._run_mode = ContextVar("run_mode", default="")
        self._request_id = ContextVar("request_id", default="")

    @classmethod
    def get_instance(cls):
        """get singleton instance."""
        if cls._instance is None:
            cls._instance = OperationContext()
        return cls._instance

    def get_user_agent(self):
        def parts():
            yield f"promptflow-sdk/{VERSION}"
            if self.user_agent:
                yield self.user_agent

        return " ".join(parts())

    @property
    def run_mode(self):
        return self._run_mode.get()

    @run_mode.setter
    def run_mode(self, run_mode: str):
        return self._run_mode.set(run_mode)

    @property
    def request_id(self):
        return self._request_id.get()

    @request_id.setter
    def request_id(self, request_id: str):
        return self._request_id.set(request_id)

    @property
    def promptflow_info(self):
        # Create a dictionary with the common promptflow info
        promptflow_info = {
            "run-mode": self.run_mode,
            "called-from": "others",  # This field will be overwritten as "aoai-tool" in built-in aoai tool
            "runtime-version": self.runtime_version,
        }

        if self.deploy_config:
            promptflow_info.update(
                {
                    "subscription-id": self.deploy_config.subscription_id,
                    "resource-group": self.deploy_config.resource_group,
                    "workspace-name": self.deploy_config.workspace_name,
                    "workspace-id": self.deploy_config.workspace_id,
                    "edition": self.deploy_config.edition,
                    "compute-type": self.deploy_config.compute_type,
                    "runtime-mode": self.deploy_config.runtime_mode,
                }
            )

        # Update the dictionary with the flow info if available
        flow = FlowExecutionContext.active_instance()
        if flow:
            promptflow_info.update(
                {
                    "flow-id": flow._flow_run_info.flow_id,
                    "root-run-id": flow._flow_run_info.root_run_id,
                    "index": flow._flow_run_info.index,
                    "run-id": flow._flow_run_info.run_id,
                    "variant-id": flow._flow_run_info.variant_id,
                }
            )

        # TODO: add flags to see whether it was coming from CI (Maybe add http headers?)

        return promptflow_info

    def get_context_dict(self) -> Dict[str, str]:
        return {
            "request_id": self.request_id,
            "run_mode": self.run_mode,
            "subscription_id": self.deploy_config.subscription_id if self.deploy_config else None,
            "resource_group": self.deploy_config.resource_group if self.deploy_config else None,
            "workspace_name": self.deploy_config.workspace_name if self.deploy_config else None,
            "compute_type": self.deploy_config.compute_type if self.deploy_config else None,
            "runtime_mode": self.deploy_config.runtime_mode if self.deploy_config else None,
            "edition": self.deploy_config.edition if self.deploy_config else None,
            "runtime_version": self.runtime_version,
        }

    def get_http_headers(self):
        # Create the header with the user agent and the promptflow info
        headers = {
            "x-ms-useragent": self.get_user_agent(),
        }

        headers.update(
            {f"ms-azure-ai-promptflow-{k}": str(v) if v is not None else "" for k, v in self.promptflow_info.items()}
        )

        return headers
