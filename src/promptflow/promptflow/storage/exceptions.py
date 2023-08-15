# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.exceptions import (
    AzureStorageOperationError,
    ErrorTarget,
    RunInfoNotFoundInStorageError,
    SystemErrorException,
    UserAuthenticationError,
    ValidationException,
)


class AzureStoragePackagesNotInstalledError(ValidationException):
    pass


class TableAuthenticationError(UserAuthenticationError):
    pass


class BlobAuthenticationError(UserAuthenticationError):
    pass


class AmlRunStorageInitError(SystemErrorException):
    """Exception raised when import package failed."""

    def __init__(
        self, message: str, target: ErrorTarget = ErrorTarget.AZURE_RUN_STORAGE
    ):
        super().__init__(message=message, target=target)


class CredentialMissing(AmlRunStorageInitError):
    pass


class MLClientMissing(AmlRunStorageInitError):
    pass


class TableInitResponseError(AzureStorageOperationError):
    pass


class BlobInitResponseError(AzureStorageOperationError):
    pass


class TableStorageInitError(AzureStorageOperationError):
    pass


class RetriableTableStorageError(AzureStorageOperationError):
    pass


class BlobStorageInitError(AzureStorageOperationError):
    pass


class RunNotFoundInTable(AzureStorageOperationError):
    pass


class CannotCreateExistingRunInTable(AzureStorageOperationError):
    pass


class CannotCreateExistingRunInBlob(AzureStorageOperationError):
    pass


class TableStorageWriteError(AzureStorageOperationError):
    pass


class StorageWriteForbidden(UserAuthenticationError):
    pass


class StorageHttpResponseError(AzureStorageOperationError):
    pass


class BlobStorageWriteError(AzureStorageOperationError):
    pass


class FailedToConvertRecordToRunInfo(AzureStorageOperationError):
    pass


class GetFlowRunError(RunInfoNotFoundInStorageError):
    pass


class GetFlowRunResponseError(RunInfoNotFoundInStorageError):
    pass


class FlowIdMissing(ValidationException):
    pass


class UnsupportedRunInfoTypeInBlob(ValidationException):
    pass


class MLFlowOperationError(SystemErrorException):
    """Exception raised when mlflow helper operation failed."""

    def __init__(
        self, message: str, target: ErrorTarget = ErrorTarget.AZURE_RUN_STORAGE
    ):
        super().__init__(message=message, target=target)


class InvalidMLFlowTrackingUri(ValidationException):
    pass


class FailedToStartRun(MLFlowOperationError):
    pass


class FailedToStartRunAfterCreated(MLFlowOperationError):
    pass


class FailedToCreateRun(MLFlowOperationError):
    pass


class FailedToEndRootRun(MLFlowOperationError):
    pass


class FailedToCancelWithAnotherActiveRun(MLFlowOperationError):
    pass


class FailedToCancelRun(MLFlowOperationError):
    pass


class CannotEndRunWithNonTerminatedStatus(MLFlowOperationError):
    pass


class FailedToGetHostCreds(MLFlowOperationError):
    pass


class RunStorageConfigMissing(ValidationException):
    pass


class PartitionKeyMissingForRunQuery(ValidationException):
    pass


def to_string(ex: Exception) -> str:
    return f"{type(ex).__name__}: {str(ex)}"


def get_status_code(exception):
    """
    Get the status code from an exception if available.

    Parameters:
        exception: The exception object from which to extract the status code.

    Returns:
        The status code if available, or None if not present.
    """
    if hasattr(exception, "status_code"):
        return exception.status_code
    elif hasattr(exception, "response") and hasattr(exception.response, "status_code"):
        return exception.response.status_code
    else:
        return None


def get_exception_type(exception):
    """Get the type of an exception."""
    return type(exception).__name__
