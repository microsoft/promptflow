# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from functools import wraps
from os import PathLike
from typing import List, Union
from pathlib import Path
from http import HTTPStatus

from promptflow._sdk._pfs_restclient.pfs_client import Client
from promptflow._sdk._service.utils.utils import get_port_from_config, is_pfs_service_healthy
from promptflow.exceptions import SystemErrorException, UserErrorException


class PFSRequestException(SystemErrorException):
    """PFSRequestException."""

    def __init__(self, message, **kwargs):
        super().__init__(message, **kwargs)


def _request_wrapper():
    """Wrapper for request. Will refresh request id and pretty print exception."""

    def exception_wrapper(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # check pfs status
            if not is_pfs_service_healthy(self._port):
                from promptflow._sdk._service.entry import entry

                entry(command_args=["start", "--port", f"{self._port}", "--force"])
                if not is_pfs_service_healthy(self._port):
                    raise UserErrorException(f"Start PFS failed on the port {self._port}, please execute \"pfs start --force\" to start the service.")
            try:
                result = func(self, *args, **kwargs)
            except Exception as e:
                raise SystemErrorException(
                    f"Calling {func.__name__} failed with exception: {e} \n"
                )
            if result.status_code not in [HTTPStatus.OK]:
                raise PFSRequestException(
                    f"Calling {func.__name__} failed \n"
                    f"Status code: {result.status_code} \n"
                    f"Error message: {result.content.decode('utf-8') } \n"
                )
            return result.parsed

        return wrapper

    return exception_wrapper


class PFSCaller:
    def __init__(self):
        self._port = get_port_from_config()
        self.client = Client(base_url=f"http://localhost:{self._port}/v1.0")

    # region Experiment

    @_request_wrapper()
    def create_experiment(self, name: str, template: Union[str, PathLike]):
        from promptflow._sdk._pfs_restclient.pfs_client.api.experiments.post_experiment import sync_detailed, PostExperimentBody
        experiment_response = sync_detailed(
            client=self.client,
            name=name,
            body=PostExperimentBody(template=Path(template).absolute().as_posix())
        )
        return experiment_response

    @_request_wrapper()
    def show_experiment(self, name: str):
        from promptflow._sdk._pfs_restclient.pfs_client.api.experiments.get_experiment import sync_detailed
        experiment_response = sync_detailed(client=self.client, name=name)
        return experiment_response

    @_request_wrapper()
    def list_experiment(self, max_results: int=None, all_results: bool=False, archived_only: bool=False, include_archived: bool = False):
        from promptflow._sdk._pfs_restclient.pfs_client.api.experiments.get_experiment_list import sync_detailed
        experiments = sync_detailed(
            client=self.client,
            max_results=max_results,
            all_results=all_results,
            archived_only=archived_only,
            include_archived=include_archived,
        )
        return experiments

    @_request_wrapper()
    def start_experiment(self, name: str, executable_path: str, from_nodes: List = None, nodes: List = None):
        from promptflow._sdk._pfs_restclient.pfs_client.api.experiments.post_experiment_start import sync_detailed, PostExperimentStartBody
        experiment_response = sync_detailed(
            client=self.client,
            name=name,
            body=PostExperimentStartBody(
                from_nodes=from_nodes,
                nodes=nodes,
                executable_path=executable_path
            )
        )
        return experiment_response

    @_request_wrapper()
    def stop_experiment(self, name: str):
        from promptflow._sdk._pfs_restclient.pfs_client.api.experiments.post_experiment_stop import sync_detailed
        experiment_response = sync_detailed(client=self.client, name=name)
        return experiment_response

    # endregion
