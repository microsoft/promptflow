import contextlib
import json
from multiprocessing import Queue

from promptflow._utils.exception_utils import ExceptionPresenter, JsonSerializedPromptflowException


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
