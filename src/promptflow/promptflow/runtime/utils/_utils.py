# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import contextlib
import json
import logging
import sys
import traceback
import zlib
from contextvars import ContextVar
from functools import lru_cache

from promptflow.contracts.azure_storage_setting import AzureStorageSetting
from promptflow.contracts.run_mode import RunMode
from promptflow.exceptions import JsonSerializedPromptflowException, PromptflowException
from promptflow.utils.internal_logger_utils import TelemetryLogHandler
from promptflow.utils.logger_utils import CredentialScrubberFormatter, FileHandlerConcurrentWrapper


FORMATTER = CredentialScrubberFormatter(
    scrub_customer_content=False,
    fmt="[%(asctime)s]  [%(process)d] %(name)-8s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_logger(
    logger_name,
    log_level: int = logging.INFO,
    std_out: bool = False,
    log_formatter: logging.Formatter = None,
) -> logging.Logger:
    logger = logging.Logger(logger_name)
    logger.setLevel(log_level)
    if std_out:
        fh = logging.StreamHandler(sys.stderr)
        if log_formatter:
            fh.setFormatter(log_formatter)
        logger.addHandler(fh)
    logger.addHandler(FileHandlerConcurrentWrapper())
    logger.addHandler(TelemetryLogHandler())
    return logger


def decode_dict(data: str) -> dict:
    # str -> bytes
    data = data.encode()
    zipped_conns = base64.b64decode(data)
    # gzip decode
    conns_data = zlib.decompress(zipped_conns, 16 + zlib.MAX_WBITS)
    return json.loads(conns_data.decode())


def encode_dict(data: dict) -> str:
    # json encode
    data = json.dumps(data)
    # gzip compress
    gzip_compress = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
    zipped_data = gzip_compress.compress(data.encode()) + gzip_compress.flush()
    # base64 encode
    b64_data = base64.b64encode(zipped_data)
    # bytes -> str
    return b64_data.decode()


@contextlib.contextmanager
def multi_processing_exception_wrapper(exception_queue):
    """Wrap the exception to a generic exception to avoid the pickle error."""
    try:
        yield
    except Exception as e:
        # func runs in a child process, any customized exception can't have extra arguments other than message
        # wrap the exception to a generic exception to avoid the pickle error
        # Ref: https://bugs.python.org/issue32696

        if not isinstance(e, PromptflowException):
            # If other errors raised, pass it into PromptflowException
            e = PromptflowException(message=str(e), error=e)
        exception_dict = e.to_dict()
        message = json.dumps(exception_dict)
        exception = JsonSerializedPromptflowException(message=message)
        exception_queue.put(exception)
        raise exception from e


@lru_cache
def get_storage_from_config(
    config,
    token=None,
    azure_storage_setting: AzureStorageSetting = None,
    run_mode: RunMode = None,
):
    return config.get_run_storage(
        workspace_access_token=token, azure_storage_setting=azure_storage_setting, run_mode=run_mode
    )


@lru_cache
def get_workspace_config(ml_client, logger):
    """Get workspace config from ml_client. Returns empty dict if failed to get config."""
    try:
        ws = ml_client.workspaces.get()
        worspace_rest = ml_client.workspaces._operation.get(
            resource_group_name=ml_client.resource_group_name, workspace_name=ml_client.workspace_name
        )

        return {
            "storage_account": ws.storage_account.split("/")[-1],
            "mt_service_endpoint": ws.discovery_url.replace("/discovery", ""),
            "resource_group": ws.resource_group,
            "subscription_id": ml_client.subscription_id,
            "workspace_name": ws.name,
            "workspace_id": worspace_rest.workspace_id,
        }
    except Exception as ex:
        logger.warning(f"Failed to get default config from ml_client: {ex}")
        logger.warning(traceback.format_exc())
        return {}


@contextlib.contextmanager
def setup_contextvar(contextvar: ContextVar, value):
    token = contextvar.set(value)
    try:
        yield
    finally:
        contextvar.reset(token)
