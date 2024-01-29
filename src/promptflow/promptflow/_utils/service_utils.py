import contextlib
import json
from multiprocessing import Queue

from promptflow._core.connection_manager import ConnectionManager
from promptflow._utils.exception_utils import ErrorResponse, ExceptionPresenter, JsonSerializedPromptflowException
from promptflow._utils.logger_utils import LogContext, logger
from promptflow.executor.service.contracts.execution_request import BaseExecutionRequest


@contextlib.contextmanager
def multi_processing_exception_wrapper(exception_queue: Queue):
    """Wrap the exception to a generic exception to avoid the pickle error."""
    try:
        yield
    except Exception as e:
        # func runs in a child process, any customized exception can't have extra arguments other than message
        # wrap the exception to a generic exception to avoid the pickle error
        # Ref: https://bugs.python.org/issue32696
        exception_dict = ExceptionPresenter.create(e).to_dict(include_debug_info=True)
        message = json.dumps(exception_dict)
        exception = JsonSerializedPromptflowException(message=message)
        exception_queue.put(exception)
        raise exception from e


def get_log_context(request: BaseExecutionRequest):
    run_mode = request.get_run_mode()
    credential_list = ConnectionManager(request.connections).get_secret_list()
    return LogContext(file_path=request.log_path, run_mode=run_mode, credential_list=credential_list)


def generate_error_response(ex):
    if isinstance(ex, JsonSerializedPromptflowException):
        error_dict = json.loads(ex.message)
    else:
        error_dict = ExceptionPresenter.create(ex).to_dict(include_debug_info=True)
    logger.exception(f"Failed to execute the flow: \n{ex}")
    return ErrorResponse.from_error_dict(error_dict)
