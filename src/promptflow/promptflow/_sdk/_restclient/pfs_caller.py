from functools import wraps

from azure.core.exceptions import HttpResponseError

from promptflow._sdk._restclient.pfs_client import PromptFlowService
from promptflow._sdk._service.utils.utils import get_port_from_config, is_pfs_service_healthy
from promptflow.exceptions import SystemErrorException


class PFSRequestException(SystemErrorException):
    """PFSRequestException."""

    def __init__(self, message, **kwargs):
        super().__init__(message, **kwargs)


def _request_wrapper():
    """Wrapper for request pretty print exception."""

    def exception_wrapper(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                # Check pfs is in health
                port = get_port_from_config()
                if not is_pfs_service_healthy(port):
                    from promptflow._sdk._service.entry import entry

                    # TODO handle pfs start failed
                    entry(["pfs", "start", "--force"])
                return func(self, *args, **kwargs)
            except HttpResponseError as e:
                raise PFSRequestException(
                    f"Calling {func.__name__} failed with request id: {self._request_id} \n"
                    f"Status code: {e.status} \n"
                    f"Reason: {e.reason} \n"
                )

        return wrapper

    return exception_wrapper


class PFSCaller:
    def __init__(self):
        # Get pfs service port
        port = get_port_from_config()
        self._client = PromptFlowService(endpoint=f"https://localhost:{port}/v1.0")

    # region experiment

    @_request_wrapper()
    def create_experiment(self, name, template):
        request_body = {
            "template": template,
        }
        return self._client.post.experiment(name=name, body=request_body)

    @_request_wrapper()
    def start_experiment(self, name, from_nodes=None, nodes=None, executable_path=None):
        request_body = {
            "from_nodes": from_nodes,
            "nodes": nodes,
            "executable_path": executable_path,
        }
        return self._client.post.experiment_start(name=name, body=request_body)

    @_request_wrapper()
    def stop_experiment(self, name):
        return self._client.get.experiment_stop(name, body=None)

    @_request_wrapper()
    def get_experiment(self, name):
        return self._client.get.experiment(name, body=None)

    # endregion
