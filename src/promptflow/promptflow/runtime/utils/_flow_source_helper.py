import os
import re
import subprocess

from promptflow._constants import ComputeType
from promptflow.contracts.runtime import AzureFileShareInfo
from promptflow.runtime.error_codes import (
    AzureFileShareAuthenticationError,
    AzureFileShareNotFoundError,
    AzureFileShareSystemError,
)
from promptflow.utils.credential_scrubber import CredentialScrubber
from promptflow.utils.retry_utils import retry

from . import logger

AZCOPY_EXE = os.environ.get("AZCOPY_EXECUTABLE", "azcopy")
CI_MOUNTED_ROOT = "/mnt/cloud/code"

ERROR_CODE_PATTERN = re.compile(r"Code: (.*?)\n")
ERROR_DESCRIPTION_PATTERN = re.compile(r"Description=(.*?)\n")


def fill_working_dir(compute_type: ComputeType, flow_source_info: AzureFileShareInfo, run_id: str):
    working_dir = flow_source_info.working_dir
    runtime_dir = working_dir
    if compute_type == ComputeType.COMPUTE_INSTANCE:
        runtime_dir = os.path.join(CI_MOUNTED_ROOT, working_dir)
    elif compute_type == ComputeType.MANAGED_ONLINE_DEPLOYMENT:
        runtime_dir = os.path.join("requests", run_id)
        os.makedirs(runtime_dir, exist_ok=True)
        sas_url = flow_source_info.sas_url
        _download_azure_file_share(sas_url, runtime_dir, run_id)

    return runtime_dir


@retry(AzureFileShareSystemError, tries=3, logger=logger)
def _download_azure_file_share(sas_url, runtime_dir, run_id):
    cmd = '%s copy "%s" "%s" --recursive' % (AZCOPY_EXE, sas_url, runtime_dir)
    file_share_url = sas_url[: sas_url.find("?")]
    logger.info(
        "Start azcopy copy the sasurl. file share url: {customer_content}. runtime_dir: %s",
        runtime_dir,
        extra={"customer_content": file_share_url},
    )
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = p.communicate()
    credential_scrubber = CredentialScrubber()
    stdout = credential_scrubber.scrub(stdout.decode())
    stderr = credential_scrubber.scrub(stderr.decode())

    logger.info("Azcopy for run %s stdout: {customer_content}", run_id, extra={"customer_content": stdout})
    if len(stderr) > 0:
        logger.error("Azcopy for run %s stderr: {customer_content}", run_id, extra={"customer_content": stderr})

    if p.returncode != 0:
        logger.error("Azcopy failed to download for run %s. Return code: %s", run_id, p.returncode)
        error_message = "\n".join([stdout, stderr])
        _handle_azcopy_error_messages(error_message)


def _handle_azcopy_error_messages(error_message):
    error_code_line = ERROR_CODE_PATTERN.search(error_message)
    if error_code_line is not None:
        error_code = error_code_line.group(1)
        description_line = ERROR_DESCRIPTION_PATTERN.search(error_message)
        if description_line is not None:
            description = description_line.group(1)
        else:
            description = error_code
        message_format = "Download azure file share failed. Code: {error_code}. Description: {description}"
        logger.error(f"Download azure file share failed. Code: {error_code}.")
        if error_code in ["AuthenticationFailed", "AuthorizationPermissionMismatch"]:
            raise AzureFileShareAuthenticationError(
                message_format=message_format, error_code=error_code, description=description
            )
        elif error_code == "ResourceNotFound":
            raise AzureFileShareNotFoundError(
                message_format=message_format, error_code=error_code, description=description
            )
        else:
            raise AzureFileShareSystemError(
                message_format=message_format, error_code=error_code, description=description
            )
    raise AzureFileShareSystemError(message=error_message)
