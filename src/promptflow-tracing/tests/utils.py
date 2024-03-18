import traceback
from multiprocessing import Queue, get_context

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import set_tracer_provider


def execute_function_in_subprocess(func, *args, **kwargs):
    """
    Execute a function in a new process and return any exception that occurs.
    Replace pickle with dill for better serialization capabilities.
    """
    ctx = get_context("spawn")
    error_queue = ctx.Queue()
    process = ctx.Process(target=_run_in_subprocess, args=(error_queue, func, args, kwargs))
    process.start()
    process.join()  # Wait for the process to finish

    if not error_queue.empty():
        err, stacktrace_str = error_queue.get()
        raise Exception(f"An error occurred in the subprocess: {err}\nStacktrace:\n{stacktrace_str}")
    assert process.exitcode == 0, f"Subprocess exited with code {process.exitcode}"


def _run_in_subprocess(error_queue: Queue, func, args, kwargs):
    try:
        func(*args, **kwargs)
    except BaseException as e:
        error_queue.put((repr(e), traceback.format_exc()))


def prepare_memory_exporter():
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    set_tracer_provider(provider)
    return exporter
