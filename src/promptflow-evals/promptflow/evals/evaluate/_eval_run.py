# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# import contextlib
import dataclasses
import enum
import logging
import os
import posixpath
import requests
import time
import uuid
from typing import Any, Dict, Optional, Type
from urllib.parse import urlparse

from azure.storage.blob import BlobServiceClient
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from promptflow.evals._version import VERSION
from promptflow._sdk.entities import Run

from azure.ai.ml.entities._credentials import AccountKeyConfiguration
from azure.ai.ml.entities._datastore.datastore import Datastore


LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class RunInfo:
    """
    A holder for run info, needed for logging.
    """

    run_id: str
    experiment_id: str
    run_name: str

    @staticmethod
    def generate(run_name: Optional[str]) -> 'RunInfo':
        """
        Generate the new RunInfo instance with the RunID and Experiment ID.

        **Note:** This code is used when we are in failed state and cannot get a run.
        :param run_name: The name of a run.
        :type run_name: str
        """
        return RunInfo(
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            run_name or ""
        )


class RunStatus(enum.Enum):
    """Run states."""
    NOT_STARTED = 0
    STARTED = 1
    BROKEN = 2
    TERMINATED = 3


class Singleton(type):
    """Singleton class, which will be used as a metaclass."""

    _instances = {}

    def __call__(cls, *args, **kwargs):
        """Redefinition of call to return one instance per type."""
        if cls not in Singleton._instances:
            Singleton._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return Singleton._instances[cls]

    @staticmethod
    def destroy(cls: Type) -> None:
        """
        Destroy the singleton instance.

        :param cls: The class to be destroyed.
        """
        Singleton._instances.pop(cls, None)


class EvalRun(metaclass=Singleton):
    """
    The simple singleton run class, used for accessing artifact store.

    :param run_name: The name of the run.
    :type run_name: Optional[str]
    :param tracking_uri: Tracking URI for this run; required to make calls.
    :type tracking_uri: str
    :param subscription_id: The subscription ID used to track run.
    :type subscription_id: str
    :param group_name: The resource group used to track run.
    :type group_name: str
    :param workspace_name: The name of workspace/project used to track run.
    :type workspace_name: str
    :param ml_client: The ml client used for authentication into Azure.
    :type ml_client: MLClient
    :param promptflow_run: The promptflow run used by the
    """

    _MAX_RETRIES = 5
    _BACKOFF_FACTOR = 2
    _TIMEOUT = 5
    _SCOPE = "https://management.azure.com/.default"

    EVALUATION_ARTIFACT = 'instance_results.jsonl'
    EVALUATION_ARTIFACT_DUMMY_RUN = 'eval_results.jsonl'

    def __init__(self,
                 run_name: Optional[str],
                 tracking_uri: str,
                 subscription_id: str,
                 group_name: str,
                 workspace_name: str,
                 ml_client: Any,
                 promptflow_run: Optional[Run] = None,
                 ):
        """
        Constructor
        """

        self._tracking_uri: str = tracking_uri
        self._subscription_id: str = subscription_id
        self._resource_group_name: str = group_name
        self._workspace_name: str = workspace_name
        self._ml_client: Any = ml_client
        self._is_promptflow_run: bool = promptflow_run is not None
        self._run_name = run_name
        self._promptflow_run = promptflow_run
        self._status = RunStatus.NOT_STARTED

    @property
    def status(self) -> RunStatus:
        """
        Return the run status.

        :return: The status of the run.
        """
        return self._status

    def _get_scope(self) -> str:
        """
        Return the scope information for the workspace.

        :param workspace_object: The workspace object.
        :type workspace_object: azureml.core.workspace.Workspace
        :return: The scope information for the workspace.
        :rtype: str
        """
        return (
            "/subscriptions/{}/resourceGroups/{}/providers" "/Microsoft.MachineLearningServices" "/workspaces/{}"
        ).format(
            self._subscription_id,
            self._resource_group_name,
            self._workspace_name,
        )

    def start_run(self) -> None:
        """
        Start the run, or, if it is not applicable (for example, if tracking is not enabled), mark it as started.
        """
        self._status = RunStatus.STARTED
        if self._tracking_uri is None:
            LOGGER.warning("tracking_uri was not provided, "
                           "The results will be saved locally, but will not be logged to Azure.")
            self._url_base = None
            self._status = RunStatus.BROKEN
            self.info = RunInfo.generate(self._run_name)
        else:
            self._url_base = urlparse(self._tracking_uri).netloc
            if self._promptflow_run is not None:
                self.info = RunInfo(
                    self._promptflow_run.name,
                    self._promptflow_run._experiment_name,
                    self._promptflow_run.name
                )
            else:
                self._status = self._start_run(self._run_name)

    def _start_run(self, run_name: Optional[str]) -> 'RunStatus':
        """
        Make a request to start the mlflow run. If the run will not start, it will be

        marked as broken and the logging will be switched off.
        :param run_name: The display name for the run.
        :type run_name: Optional[str]
        :returns: True if the run has started and False otherwise.
        """
        url = f"https://{self._url_base}/mlflow/v2.0" f"{self._get_scope()}/api/2.0/mlflow/runs/create"
        body = {
            "experiment_id": "0",
            "user_id": "promptflow-evals",
            "start_time": int(time.time() * 1000),
            "tags": [{"key": "mlflow.user", "value": "promptflow-evals"}],
        }
        if run_name:
            body["run_name"] = run_name
        response = self.request_with_retry(
            url=url,
            method='POST',
            json_dict=body
        )
        if response.status_code != 200:
            self.info = RunInfo.generate(run_name)
            LOGGER.warning(f"The run failed to start: {response.status_code}: {response.text}."
                           "The results will be saved locally, but will not be logged to Azure.")
            return RunStatus.BROKEN
        parsed_response = response.json()
        self.info = RunInfo(
            run_id=parsed_response['run']['info']['run_id'],
            experiment_id=parsed_response['run']['info']['experiment_id'],
            run_name=parsed_response['run']['info']['run_name']
        )
        return RunStatus.STARTED

    def end_run(self, reason: str) -> None:
        """
        Tetminate the run.

        :param reason: One of "FINISHED" "FAILED" and "KILLED"
        :type reason: str
        :raises: ValueError if the run is not in ("FINISHED", "FAILED", "KILLED")
        """
        self._raise_not_started_nay_be()
        if self._is_promptflow_run:
            # This run is already finished, we just add artifacts/metrics to it.
            self._status = RunStatus.TERMINATED
            Singleton.destroy(EvalRun)
            return
        if reason not in ("FINISHED", "FAILED", "KILLED"):
            raise ValueError(
                f"Incorrect terminal status {reason}. " 'Valid statuses are "FINISHED", "FAILED" and "KILLED".'
            )
        if self._status == RunStatus.TERMINATED:
            LOGGER.warning("Unable to stop run because it was already terminated.")
            return
        if self._status == RunStatus.BROKEN:
            LOGGER.warning("Unable to stop run because the run failed to start.")
            return
        url = f"https://{self._url_base}/mlflow/v2.0" f"{self._get_scope()}/api/2.0/mlflow/runs/update"
        body = {
            "run_uuid": self.info.run_id,
            "status": reason,
            "end_time": int(time.time() * 1000),
            "run_id": self.info.run_id,
        }
        response = self.request_with_retry(url=url, method="POST", json_dict=body)
        if response.status_code != 200:
            LOGGER.warning("Unable to terminate the run.")
        Singleton.destroy(EvalRun)
        self._status = RunStatus.TERMINATED

    def __enter__(self):
        """The Context Manager enter call."""
        self.start_run()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """The context manager exit call."""
        self.start_run()

    def get_run_history_uri(self) -> str:
        """
        Return the run history service URI.
        """
        return (
            f"https://{self._url_base}"
            "/history/v1.0"
            f"{self._get_scope()}"
            f"/experimentids/{self.info.experiment_id}/runs/{self.info.run_id}"
        )

    def get_artifacts_uri(self) -> str:
        """
        Returns the url to upload the artifacts.
        """
        return self.get_run_history_uri() + "/artifacts/batch/metadata"

    def get_metrics_url(self):
        """
        Return the url needed to track the mlflow metrics.
        """
        return f"https://{self._url_base}" "/mlflow/v2.0" f"{self._get_scope()}" f"/api/2.0/mlflow/runs/log-metric"

    def _get_token(self):
        # We have to use lazy import because promptflow.azure
        # is an optional dependency.
        from promptflow.azure._utils._token_cache import ArmTokenCache
        return ArmTokenCache().get_token(self._ml_client._credential)

    def request_with_retry(
        self, url: str, method: str, json_dict: Dict[str, Any], headers: Optional[Dict[str, str]] = None
    ) -> requests.Response:
        """
        Send the request with retries.

        :param url: The url to send the request to.
        :type url: str
        :param auth_token: Azure authentication token
        :type auth_token: str or None
        :param method: The request method to be used.
        :type method: str
        :param json_dict: The json dictionary (not serialized) to be sent.
        :type json_dict: dict.
        :return: The requests.Response object.
        """
        if headers is None:
            headers = {}
        headers["User-Agent"] = f"promptflow/{VERSION}"
        headers["Authorization"] = f"Bearer {self._get_token()}"
        retry = Retry(
            total=EvalRun._MAX_RETRIES,
            connect=EvalRun._MAX_RETRIES,
            read=EvalRun._MAX_RETRIES,
            redirect=EvalRun._MAX_RETRIES,
            status=EvalRun._MAX_RETRIES,
            status_forcelist=(408, 429, 500, 502, 503, 504),
            backoff_factor=EvalRun._BACKOFF_FACTOR,
            allowed_methods=None,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session = requests.Session()
        session.mount("https://", adapter)
        return session.request(method, url, headers=headers, json=json_dict, timeout=EvalRun._TIMEOUT)

    def _log_warning(self, failed_op: str, response: requests.Response) -> None:
        """
        Log the error if request was not successful.

        :param failed_op: The user-friendly message for the failed operation.
        :type failed_op: str
        :param response: The request.
        :type response: requests.Response
        """
        LOGGER.warning(
            f"Unable to {failed_op}, "
            f"the request failed with status code {response.status_code}, "
            f"{response.text=}."
        )

    def _raise_not_started_nay_be(self) -> None:
        """
        Raise value error if the run was not started.

        :raises: ValueError
        """
        if self._status == RunStatus.NOT_STARTED:
            raise ValueError(
                "The run did not started. "
                "Please start the run by calling start_run method.")

    def log_artifact(self, artifact_folder: str, artifact_name: str = EVALUATION_ARTIFACT) -> None:
        """
        The local implementation of mlflow-like artifact logging.

        **Note:** In the current implementation we are not using the thread pool executor
        as it is done in azureml-mlflow, instead we are just running upload in cycle as we are not
        expecting uploading a lot of artifacts.
        :param artifact_folder: The folder with artifacts to be uploaded.
        :type artifact_folder: str
        """
        self._raise_not_started_nay_be()
        if self._status == RunStatus.BROKEN:
            LOGGER.warning("Unable to log artifact because the run failed to start.")
            return
        # Check if artifact dirrectory is empty or does not exist.
        if not os.path.isdir(artifact_folder):
            LOGGER.warning("The path to the artifact is either not a directory or does not exist.")
            return
        if not os.listdir(artifact_folder):
            LOGGER.warning("The path to the artifact is empty.")
            return
        if not os.path.isfile(os.path.join(artifact_folder, artifact_name)):
            LOGGER.warning("The run results file was not found, skipping artifacts upload.")
            return
        # First we will list the files and the appropriate remote paths for them.
        root_upload_path = posixpath.join("promptflow", 'PromptFlowArtifacts', self.info.run_name)
        remote_paths = {'paths': []}
        local_paths = []
        # Go over the artifact folder and upload all artifacts.
        for (root, _, filenames) in os.walk(artifact_folder):
            upload_path = root_upload_path
            if root != artifact_folder:
                rel_path = os.path.relpath(root, artifact_folder)
                if rel_path != '.':
                    upload_path = posixpath.join(root_upload_path, rel_path)
            for f in filenames:
                remote_file_path = posixpath.join(upload_path, f)
                remote_paths["paths"].append({"path": remote_file_path})
                local_file_path = os.path.join(root, f)
                local_paths.append(local_file_path)

        # We will write the artifacts to the workspaceblobstore
        datastore = self._ml_client.datastores.get_default(include_secrets=True)
        account_url = f"{datastore.account_name}.blob.{datastore.endpoint}"
        svc_client = BlobServiceClient(
            account_url=account_url, credential=self._get_datastore_credential(datastore))
        for local, remote in zip(local_paths, remote_paths['paths']):
            blob_client = svc_client.get_blob_client(
                container=datastore.container_name,
                blob=remote['path'])
            with open(local, 'rb') as fp:
                blob_client.upload_blob(fp, overwrite=True)

        # To show artifact in UI we will need to register it. If it is a promptflow run,
        # we are rewriting already registered artifact and need to skip this step.
        if self._is_promptflow_run:
            return
        url = (
            f"https://{self._url_base}/artifact/v2.0/subscriptions/{self._subscription_id}"
            f"/resourceGroups/{self._resource_group_name}/providers/"
            f"Microsoft.MachineLearningServices/workspaces/{self._workspace_name}/artifacts/register"
        )

        response = self.request_with_retry(
            url=url,
            method="POST",
            json_dict={
                "origin": "ExperimentRun",
                "container": f"dcid.{self.info.run_id}",
                "path": artifact_name,
                "dataPath": {
                    "dataStoreName": datastore.name,
                    "relativePath": posixpath.join(root_upload_path, artifact_name),
                },
            },
        )
        if response.status_code != 200:
            self._log_warning('register artifact', response)

    def _get_datastore_credential(self, datastore: Datastore):
        # Reference the logic in azure.ai.ml._artifact._artifact_utilities
        # https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ml/azure-ai-ml/azure/ai/ml/_artifacts/_artifact_utilities.py#L103
        credential = datastore.credentials
        if isinstance(credential, AccountKeyConfiguration):
            return credential.account_key
        elif hasattr(credential, "sas_token"):
            return credential.sas_token
        else:
            return self._ml_client.datastores._credential

    def log_metric(self, key: str, value: float) -> None:
        """
        Log the metric to azure similar to how it is done by mlflow.

        :param key: The metric name to be logged.
        :type key: str
        :param value: The valure to be logged.
        :type value: float
        """
        self._raise_not_started_nay_be()
        if self._status == RunStatus.BROKEN:
            LOGGER.warning("Unable to log metric because the run failed to start.")
            return
        body = {
            "run_uuid": self.info.run_id,
            "key": key,
            "value": value,
            "timestamp": int(time.time() * 1000),
            "step": 0,
            "run_id": self.info.run_id,
        }
        response = self.request_with_retry(
            url=self.get_metrics_url(),
            method="POST",
            json_dict=body,
        )
        if response.status_code != 200:
            self._log_warning("save metrics", response)

    def write_properties_to_run_history(self, properties: Dict[str, Any]) -> None:
        """
        Write properties to the RunHistory service.

        :param properties: The properties to be written to run history.
        :type properties: dict
        """
        self._raise_not_started_nay_be()
        if self._status == RunStatus.BROKEN:
            LOGGER.warning("Unable to write properties because the run failed to start.")
            return
        # update host to run history and request PATCH API
        response = self.request_with_retry(
            url=self.get_run_history_uri(),
            method="PATCH",
            json_dict={"runId": self.info.run_id, "properties": properties},
        )
        if response.status_code != 200:
            LOGGER.error("Fail writing properties '%s' to run history: %s", properties, response.text)

    @staticmethod
    def get_instance(*args, **kwargs) -> "EvalRun":
        """
        The convenience method to the the EvalRun instance.

        :return: The EvalRun instance.
        """
        return EvalRun(*args, **kwargs)
