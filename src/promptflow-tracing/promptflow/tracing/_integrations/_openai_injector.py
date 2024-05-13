# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import functools
import importlib
import json
import logging
import os
from importlib.metadata import version

import openai

from .._operation_context import OperationContext
from .._trace import _traced_async, _traced_sync
from ..contracts.trace import TraceType

USER_AGENT_HEADER = "x-ms-useragent"
PROMPTFLOW_HEADER = "ms-azure-ai-promptflow"
IS_LEGACY_OPENAI = version("openai").startswith("0.")


def inject_function_async(args_to_ignore=None, trace_type=TraceType.LLM, name=None):
    def decorator(func):
        return _traced_async(func, args_to_ignore=args_to_ignore, trace_type=trace_type, name=name)

    return decorator


def inject_function_sync(args_to_ignore=None, trace_type=TraceType.LLM, name=None):
    def decorator(func):
        return _traced_sync(func, args_to_ignore=args_to_ignore, trace_type=trace_type, name=name)

    return decorator


def get_aoai_telemetry_headers() -> dict:
    """Get the http headers for AOAI request.

    The header, whose name starts with "ms-azure-ai-" or "x-ms-", is used to track the request in AOAI. The
    value in this dict will be recorded as telemetry, so please do not put any sensitive information in it.

    Returns:
        A dictionary of http headers.
    """

    # get promptflow info from operation context
    operation_context = OperationContext.get_instance()
    tracking_info = operation_context._get_tracking_info()

    def is_primitive(value):
        return value is None or isinstance(value, (int, float, str, bool))

    #  Ensure that the telemetry info is primitive
    tracking_info = {k: v for k, v in tracking_info.items() if is_primitive(v)}

    # init headers
    headers = {USER_AGENT_HEADER: operation_context.get_user_agent()}

    # update header with promptflow info
    headers[PROMPTFLOW_HEADER] = json.dumps(tracking_info)

    return headers


def inject_operation_headers(f):
    def inject_headers(kwargs):
        # Inject headers from operation context, overwrite injected header with headers from kwargs.
        injected_headers = get_aoai_telemetry_headers()
        original_headers = kwargs.get("headers" if IS_LEGACY_OPENAI else "extra_headers")
        if original_headers and isinstance(original_headers, dict):
            injected_headers.update(original_headers)
        kwargs["headers" if IS_LEGACY_OPENAI else "extra_headers"] = injected_headers

    if asyncio.iscoroutinefunction(f):

        @functools.wraps(f)
        async def wrapper(*args, **kwargs):
            inject_headers(kwargs)
            return await f(*args, **kwargs)

    else:

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            inject_headers(kwargs)
            return f(*args, **kwargs)

    return wrapper


def inject_async(f, trace_type, name):
    wrapper_fun = inject_operation_headers(
        (inject_function_async(["api_key", "headers", "extra_headers"], trace_type, name)(f))
    )
    wrapper_fun._original = f
    return wrapper_fun


def inject_sync(f, trace_type, name):
    wrapper_fun = inject_operation_headers(
        (inject_function_sync(["api_key", "headers", "extra_headers"], trace_type, name)(f))
    )
    wrapper_fun._original = f
    return wrapper_fun


def _legacy_openai_apis():
    sync_apis = (
        ("openai", "Completion", "create", TraceType.LLM, "openai_completion_legacy"),
        ("openai", "ChatCompletion", "create", TraceType.LLM, "openai_chat_legacy"),
        ("openai", "Embedding", "create", TraceType.EMBEDDING, "openai_embedding_legacy"),
    )
    async_apis = (
        ("openai", "Completion", "acreate", TraceType.LLM, "openai_completion_legacy"),
        ("openai", "ChatCompletion", "acreate", TraceType.LLM, "openai_chat_legacy"),
        ("openai", "Embedding", "acreate", TraceType.EMBEDDING, "openai_embedding_legacy"),
    )
    return sync_apis, async_apis


def _openai_apis():
    sync_apis = (
        ("openai.resources.chat", "Completions", "create", TraceType.LLM, "openai_chat"),
        ("openai.resources", "Completions", "create", TraceType.LLM, "openai_completion"),
        ("openai.resources", "Embeddings", "create", TraceType.EMBEDDING, "openai_embeddings"),
        ("openai.resources", "Files", "create", TraceType.FILE, "openai_file_create"),
        ("openai.resources", "Files", "retrieve", TraceType.FILE, "openai_file_retrieve"),
        ("openai.resources", "Files", "list", TraceType.FILE, "openai_file_list"),
        ("openai.resources", "Files", "delete", TraceType.FILE, "openai_file_delete"),
        ("openai.resources", "Files", "content", TraceType.FILE, "openai_file_content"),
        ("openai.resources", "Files", "retrieve_content", TraceType.FILE, "openai_file_retrieve_content"),
        ("openai.resources", "Files", "wait_for_processing", TraceType.FILE, "openai_file_wait_for_processing"),
        ("openai.resources", "AsyncFiles", "list", TraceType.ASSISTANT, "openai_file_list"),
        ("openai.resources.beta.assistants", "Assistants", "create", TraceType.ASSISTANT, "openai_assistant_create"),
        (
            "openai.resources.beta.assistants",
            "Assistants",
            "retrieve",
            TraceType.ASSISTANT,
            "openai_assistant_retrieve",
        ),
        ("openai.resources.beta.assistants", "Assistants", "update", TraceType.ASSISTANT, "openai_assistant_update"),
        ("openai.resources.beta.assistants", "Assistants", "list", TraceType.ASSISTANT, "openai_assistant_list"),
        ("openai.resources.beta.assistants", "Assistants", "delete", TraceType.ASSISTANT, "openai_assistant_delete"),
        ("openai.resources.beta.assistants", "AsyncAssistants", "list", TraceType.ASSISTANT, "openai_assistant_list"),
        ("openai.resources.beta.threads", "Threads", "create", TraceType.THREAD, "openai_thread_create"),
        ("openai.resources.beta.threads", "Threads", "retrieve", TraceType.THREAD, "openai_thread_retrieve"),
        ("openai.resources.beta.threads", "Threads", "update", TraceType.THREAD, "openai_thread_update"),
        ("openai.resources.beta.threads", "Threads", "delete", TraceType.THREAD, "openai_thread_delete"),
        (
            "openai.resources.beta.threads",
            "Threads",
            "create_and_run",
            TraceType.THREAD,
            "openai_thread_create_and_run",
        ),
        (
            "openai.resources.beta.threads",
            "Threads",
            "create_and_run_stream",
            TraceType.THREAD,
            "openai_thread_create_and_run_stream",
        ),
        (
            "openai.resources.beta.threads",
            "AsyncThreads",
            "create_and_run_stream",
            TraceType.THREAD,
            "openai_thread_create_and_run_stream",
        ),
        ("openai.resources.beta.threads.messages", "Messages", "create", TraceType.MESSAGE, "openai_message_create"),
        (
            "openai.resources.beta.threads.messages",
            "Messages",
            "retrieve",
            TraceType.MESSAGE,
            "openai_message_retrieve",
        ),
        ("openai.resources.beta.threads.messages", "Messages", "update", TraceType.MESSAGE, "openai_message_update"),
        ("openai.resources.beta.threads.messages", "Messages", "list", TraceType.MESSAGE, "openai_message_list"),
        ("openai.resources.beta.threads.messages", "AsyncMessages", "list", TraceType.MESSAGE, "openai_message_list"),
        ("openai.resources.beta.threads.runs", "Runs", "create", TraceType.RUN, "openai_run_create"),
        ("openai.resources.beta.threads.runs", "Runs", "retrieve", TraceType.RUN, "openai_run_retrieve"),
        ("openai.resources.beta.threads.runs", "Runs", "update", TraceType.RUN, "openai_run_update"),
        ("openai.resources.beta.threads.runs", "Runs", "list", TraceType.RUN, "openai_run_list"),
        ("openai.resources.beta.threads.runs", "Runs", "cancel", TraceType.RUN, "openai_run_cancel"),
        ("openai.resources.beta.threads.runs", "Runs", "create_and_poll", TraceType.RUN, "openai_run_create_and_poll"),
        (
            "openai.resources.beta.threads.runs",
            "Runs",
            "create_and_stream",
            TraceType.RUN,
            "openai_run_create_and_stream",
        ),
        ("openai.resources.beta.threads.runs", "Runs", "poll", TraceType.RUN, "openai_run_poll"),
        ("openai.resources.beta.threads.runs", "Runs", "stream", TraceType.RUN, "openai_run_stream"),
        (
            "openai.resources.beta.threads.runs",
            "Runs",
            "submit_tool_outputs",
            TraceType.RUN,
            "openai_run_submit_tool_outputs",
        ),
        (
            "openai.resources.beta.threads.runs",
            "Runs",
            "submit_tool_outputs_and_poll",
            TraceType.RUN,
            "openai_run_submit_tool_outputs_and_poll",
        ),
        (
            "openai.resources.beta.threads.runs",
            "Runs",
            "submit_tool_outputs_stream",
            TraceType.RUN,
            "openai_run_submit_tool_outputs_stream",
        ),
        ("openai.resources.beta.threads.runs", "AsyncRuns", "list", TraceType.RUN, "openai_run_list"),
        ("openai.resources.beta.threads.runs", "AsyncRuns", "stream", TraceType.RUN, "openai_run_stream"),
        (
            "openai.resources.beta.threads.runs",
            "AsyncRuns",
            "create_and_stream",
            TraceType.RUN,
            "openai_run_create_and_stream",
        ),
        (
            "openai.resources.beta.threads.runs",
            "AsyncRuns",
            "submit_tool_outputs_stream",
            TraceType.RUN,
            "openai_run_submit_tool_outputs_stream",
        ),
        ("openai.resources.beta.threads.runs", "Steps", "retrieve", TraceType.RUN, "openai_run_step_retrieve"),
        ("openai.resources.beta.threads.runs", "Steps", "list", TraceType.RUN, "openai_run_steps_list"),
        ("openai.resources.beta.threads.runs", "AsyncSteps", "list", TraceType.RUN, "openai_run_steps_list"),
        (
            "openai.resources.beta.vector_stores",
            "FileBatches",
            "create",
            TraceType.VECTOR_STORE,
            "openai_file_batch_create",
        ),
        (
            "openai.resources.beta.vector_stores",
            "FileBatches",
            "retrieve",
            TraceType.VECTOR_STORE,
            "openai_file_batch_retrieve",
        ),
        (
            "openai.resources.beta.vector_stores",
            "FileBatches",
            "cancel",
            TraceType.VECTOR_STORE,
            "openai_file_batch_cancel",
        ),
        (
            "openai.resources.beta.vector_stores",
            "FileBatches",
            "create_and_poll",
            TraceType.VECTOR_STORE,
            "openai_file_batch_create_and_poll",
        ),
        (
            "openai.resources.beta.vector_stores",
            "FileBatches",
            "list_files",
            TraceType.VECTOR_STORE,
            "openai_file_batch_list_files",
        ),
        (
            "openai.resources.beta.vector_stores",
            "FileBatches",
            "poll",
            TraceType.VECTOR_STORE,
            "openai_file_batch_poll",
        ),
        (
            "openai.resources.beta.vector_stores",
            "FileBatches",
            "upload_and_poll",
            TraceType.VECTOR_STORE,
            "openai_file_batch_upload_and_poll",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncFileBatches",
            "list_files",
            TraceType.VECTOR_STORE,
            "openai_file_batch_list_files",
        ),
        ("openai.resources.beta.vector_stores", "Files", "create", TraceType.VECTOR_STORE, "openai_file_create"),
        ("openai.resources.beta.vector_stores", "Files", "retrieve", TraceType.VECTOR_STORE, "openai_file_retrieve"),
        ("openai.resources.beta.vector_stores", "Files", "list", TraceType.VECTOR_STORE, "openai_file_list"),
        ("openai.resources.beta.vector_stores", "Files", "delete", TraceType.VECTOR_STORE, "openai_file_delete"),
        (
            "openai.resources.beta.vector_stores",
            "Files",
            "create_and_poll",
            TraceType.VECTOR_STORE,
            "openai_file_create_and_poll",
        ),
        ("openai.resources.beta.vector_stores", "Files", "poll", TraceType.VECTOR_STORE, "openai_file_poll"),
        ("openai.resources.beta.vector_stores", "Files", "upload", TraceType.VECTOR_STORE, "openai_file_upload"),
        (
            "openai.resources.beta.vector_stores",
            "Files",
            "upload_and_poll",
            TraceType.VECTOR_STORE,
            "openai_file_upload_and_poll",
        ),
        ("openai.resources.beta.vector_stores", "AsyncFiles", "list", TraceType.VECTOR_STORE, "openai_file_list"),
        (
            "openai.resources.beta.vector_stores",
            "VectorStores",
            "create",
            TraceType.VECTOR_STORE,
            "openai_vector_store_create",
        ),
        (
            "openai.resources.beta.vector_stores",
            "VectorStores",
            "retrieve",
            TraceType.VECTOR_STORE,
            "openai_vector_store_retrieve",
        ),
        (
            "openai.resources.beta.vector_stores",
            "VectorStores",
            "update",
            TraceType.VECTOR_STORE,
            "openai_vector_store_update",
        ),
        (
            "openai.resources.beta.vector_stores",
            "VectorStores",
            "list",
            TraceType.VECTOR_STORE,
            "openai_vector_store_list",
        ),
        (
            "openai.resources.beta.vector_stores",
            "VectorStores",
            "delete",
            TraceType.VECTOR_STORE,
            "openai_vector_store_delete",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncVectorStores",
            "list",
            TraceType.VECTOR_STORE,
            "openai_vector_store_list",
        ),
    )
    async_apis = (
        ("openai.resources.chat", "AsyncCompletions", "create", TraceType.LLM, "openai_chat_async"),
        ("openai.resources", "AsyncCompletions", "create", TraceType.LLM, "openai_completion_async"),
        ("openai.resources", "AsyncEmbeddings", "create", TraceType.EMBEDDING, "openai_embeddings_async"),
        ("openai.resources", "AsyncFiles", "create", TraceType.ASSISTANT, "openai_file_create_async"),
        ("openai.resources", "AsyncFiles", "retrieve", TraceType.ASSISTANT, "openai_file_retrieve_async"),
        ("openai.resources", "AsyncFiles", "delete", TraceType.ASSISTANT, "openai_file_delete_async"),
        ("openai.resources", "AsyncFiles", "content", TraceType.FILE, "openai_file_content_async"),
        ("openai.resources", "AsyncFiles", "retrieve_content", TraceType.FILE, "openai_file_retrieve_content_async"),
        (
            "openai.resources",
            "AsyncFiles",
            "wait_for_processing",
            TraceType.FILE,
            "openai_file_wait_for_processing_async",
        ),
        (
            "openai.resources.beta.assistants",
            "AsyncAssistants",
            "create",
            TraceType.ASSISTANT,
            "openai_assistant_create_async",
        ),
        (
            "openai.resources.beta.assistants",
            "AsyncAssistants",
            "retrieve",
            TraceType.ASSISTANT,
            "openai_assistant_retrieve_async",
        ),
        (
            "openai.resources.beta.assistants",
            "AsyncAssistants",
            "update",
            TraceType.ASSISTANT,
            "openai_assistant_update_async",
        ),
        (
            "openai.resources.beta.assistants",
            "AsyncAssistants",
            "delete",
            TraceType.ASSISTANT,
            "openai_assistant_delete_async",
        ),
        ("openai.resources.beta.threads", "AsyncThreads", "create", TraceType.THREAD, "openai_thread_create_async"),
        ("openai.resources.beta.threads", "AsyncThreads", "retrieve", TraceType.THREAD, "openai_thread_retrieve_async"),
        ("openai.resources.beta.threads", "AsyncThreads", "update", TraceType.THREAD, "openai_thread_update_async"),
        ("openai.resources.beta.threads", "AsyncThreads", "delete", TraceType.THREAD, "openai_thread_delete_async"),
        (
            "openai.resources.beta.threads",
            "AsyncThreads",
            "create_and_run",
            TraceType.THREAD,
            "openai_thread_create_and_run_async",
        ),
        (
            "openai.resources.beta.threads",
            "AsyncThreads",
            "create_and_run_poll",
            TraceType.THREAD,
            "openai_thread_create_and_run_poll_async",
        ),
        (
            "openai.resources.beta.threads.messages",
            "AsyncMessages",
            "create",
            TraceType.MESSAGE,
            "openai_message_create_async",
        ),
        (
            "openai.resources.beta.threads.messages",
            "AsyncMessages",
            "retrieve",
            TraceType.MESSAGE,
            "openai_message_retrieve_async",
        ),
        (
            "openai.resources.beta.threads.messages",
            "AsyncMessages",
            "update",
            TraceType.MESSAGE,
            "openai_message_update_async",
        ),
        ("openai.resources.beta.threads.runs", "AsyncRuns", "create", TraceType.RUN, "openai_run_create_async"),
        ("openai.resources.beta.threads.runs", "AsyncRuns", "retrieve", TraceType.RUN, "openai_run_retrieve_async"),
        ("openai.resources.beta.threads.runs", "AsyncRuns", "update", TraceType.RUN, "openai_run_update_async"),
        ("openai.resources.beta.threads.runs", "AsyncRuns", "cancel", TraceType.RUN, "openai_run_cancel_async"),
        (
            "openai.resources.beta.threads.runs",
            "AsyncRuns",
            "create_and_poll",
            TraceType.RUN,
            "openai_run_create_and_poll_async",
        ),
        ("openai.resources.beta.threads.runs", "AsyncRuns", "poll", TraceType.RUN, "openai_run_poll_async"),
        (
            "openai.resources.beta.threads.runs",
            "AsyncRuns",
            "submit_tool_outputs",
            TraceType.RUN,
            "openai_run_submit_tool_outputs_async",
        ),
        (
            "openai.resources.beta.threads.runs",
            "AsyncRuns",
            "submit_tool_outputs_and_poll",
            TraceType.RUN,
            "openai_run_submit_tool_outputs_and_poll_async",
        ),
        (
            "openai.resources.beta.threads.runs",
            "AsyncSteps",
            "retrieve",
            TraceType.RUN,
            "openai_run_step_retrieve_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncFileBatches",
            "create",
            TraceType.VECTOR_STORE,
            "openai_file_batch_create_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncFileBatches",
            "retrieve",
            TraceType.VECTOR_STORE,
            "openai_file_batch_retrieve_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncFileBatches",
            "cancel",
            TraceType.VECTOR_STORE,
            "openai_file_batch_cancel_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncFileBatches",
            "create_and_poll",
            TraceType.VECTOR_STORE,
            "openai_file_batch_create_and_poll_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncFileBatches",
            "poll",
            TraceType.VECTOR_STORE,
            "openai_file_batch_poll_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncFileBatches",
            "upload_and_poll",
            TraceType.VECTOR_STORE,
            "openai_file_batch_upload_and_poll_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncFiles",
            "create",
            TraceType.VECTOR_STORE,
            "openai_file_create_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncFiles",
            "retrieve",
            TraceType.VECTOR_STORE,
            "openai_file_retrieve_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncFiles",
            "delete",
            TraceType.VECTOR_STORE,
            "openai_file_delete_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncFiles",
            "create_and_poll",
            TraceType.VECTOR_STORE,
            "openai_file_create_and_poll_async",
        ),
        ("openai.resources.beta.vector_stores", "AsyncFiles", "poll", TraceType.VECTOR_STORE, "openai_file_poll_async"),
        (
            "openai.resources.beta.vector_stores",
            "AsyncFiles",
            "upload",
            TraceType.VECTOR_STORE,
            "openai_file_upload_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncFiles",
            "upload_and_poll",
            TraceType.VECTOR_STORE,
            "openai_file_upload_and_poll_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncVectorStores",
            "create",
            TraceType.VECTOR_STORE,
            "openai_vector_store_create_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncVectorStores",
            "retrieve",
            TraceType.VECTOR_STORE,
            "openai_vector_store_retrieve_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncVectorStores",
            "update",
            TraceType.VECTOR_STORE,
            "openai_vector_store_update_async",
        ),
        (
            "openai.resources.beta.vector_stores",
            "AsyncVectorStores",
            "delete",
            TraceType.VECTOR_STORE,
            "openai_vector_store_delete_async",
        ),
    )
    return sync_apis, async_apis


def _openai_api_list():
    if IS_LEGACY_OPENAI:
        sync_apis, async_apis = _legacy_openai_apis()
    else:
        sync_apis, async_apis = _openai_apis()
    yield sync_apis, inject_sync
    yield async_apis, inject_async


def _generate_api_and_injector(apis):
    for apis, injector in apis:
        for module_name, class_name, method_name, trace_type, name in apis:
            try:
                module = importlib.import_module(module_name)
                api = getattr(module, class_name)
                if hasattr(api, method_name):
                    yield api, method_name, trace_type, injector, name
            except AttributeError as e:
                # Log the attribute exception with the missing class information
                logging.warning(
                    f"AttributeError: The module '{module_name}' does not have the class '{class_name}'. {str(e)}"
                )
            except Exception as e:
                # Log other exceptions as a warning, as we're not sure what they might be
                logging.warning(f"An unexpected error occurred: {str(e)}")


def available_openai_apis_and_injectors():
    """
    Generates a sequence of tuples containing OpenAI API classes, method names, and
    corresponding injector functions based on whether the legacy OpenAI interface is used.

    This function handles the discrepancy reported in https://github.com/openai/openai-python/issues/996,
    where async interfaces were not recognized as coroutines. It ensures that decorators
    are applied correctly to both synchronous and asynchronous methods.

    Yields:
        Tuples of (api_class, method_name, injector_function)
    """
    yield from _generate_api_and_injector(_openai_api_list())


def inject_openai_api():
    """This function:
    1. Modifies the create methods of the OpenAI API classes to inject logic before calling the original methods.
    It stores the original methods as _original attributes of the create methods.
    2. Updates the openai api configs from environment variables.
    """

    for api, method, trace_type, injector, name in available_openai_apis_and_injectors():
        # Check if the create method of the openai_api class has already been modified
        if not hasattr(getattr(api, method), "_original"):
            setattr(api, method, injector(getattr(api, method), trace_type, name))

    if IS_LEGACY_OPENAI:
        # For the openai versions lower than 1.0.0, it reads api configs from environment variables only at
        # import time. So we need to update the openai api configs from environment variables here.
        # Please refer to this issue: https://github.com/openai/openai-python/issues/557.
        # The issue has been fixed in openai>=1.0.0.
        openai.api_key = os.environ.get("OPENAI_API_KEY", openai.api_key)
        openai.api_key_path = os.environ.get("OPENAI_API_KEY_PATH", openai.api_key_path)
        openai.organization = os.environ.get("OPENAI_ORGANIZATION", openai.organization)
        openai.api_base = os.environ.get("OPENAI_API_BASE", openai.api_base)
        openai.api_type = os.environ.get("OPENAI_API_TYPE", openai.api_type)
        openai.api_version = os.environ.get("OPENAI_API_VERSION", openai.api_version)


def recover_openai_api():
    """This function restores the original create methods of the OpenAI API classes
    by assigning them back from the _original attributes of the modified methods.
    """
    for api, method, _, _, _ in available_openai_apis_and_injectors():
        if hasattr(getattr(api, method), "_original"):
            setattr(api, method, getattr(getattr(api, method), "_original"))
