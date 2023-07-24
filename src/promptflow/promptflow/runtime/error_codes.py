from promptflow.exceptions import ErrorTarget, SystemErrorException, UserAuthenticationError, UserErrorException

# region runtime.runtime_config


class InvalidClientAuthentication(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class UserAuthenticationValidationError(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class MissingDeploymentConfigs(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class ConfigFileNotExists(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class InvalidRunStorageType(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


# endregion


# region runtime.runtime


class EmptyDataResolved(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class UnexpectedFlowSourceType(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


# endregion


# region runtime.data


class RuntimeConfigNotProvided(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class InvalidDataUri(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class InvalidAmlDataUri(InvalidDataUri):
    pass


class InvalidBlobDataUri(InvalidDataUri):
    pass


class InvalidWsabsDataUri(InvalidDataUri):
    pass


# endregion


# region runtime.connection


class OpenURLFailed(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class OpenURLUserAuthenticationError(UserAuthenticationError):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class OpenURLFailedUserError(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class UnknownConnectionType(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


# endregion


# region runtime.utils._snapshots_client


class SnapshotNotFound(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class GetSnapshotSasUrlFailed(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class DownloadSnapshotFailed(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


# endregion


# region runtime.utils._flow_source_helper


class AzureFileShareAuthenticationError(UserAuthenticationError):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class AzureFileShareNotFoundError(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class AzureFileShareSystemError(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


# endregion


# region runtime.app


class GenerateMetaUserError(UserErrorException):
    """Base exception raised when failed to validate tool."""

    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class MetaFileNotFound(GenerateMetaUserError):
    pass


class GenerateMetaTimeout(GenerateMetaUserError):
    pass


class GenerateMetaSystemError(SystemErrorException):
    """Base exception raised when failed to validate tool."""

    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class NoToolTypeDefined(GenerateMetaSystemError):
    pass


class MetaFileReadError(GenerateMetaSystemError):
    pass


class RuntimeTerminatedByUser(UserErrorException):
    def __init__(self, message):
        super().__init__(message, target=ErrorTarget.RUNTIME)


# endregion


# region utils.run_result_parser


class RunResultParseError(SystemErrorException):
    """Exception raised when failed to parse run result.

    We parse the run result to extract the run error.
    The error message is then populated in the response body.

    This exception is a SystemError since the extraction should always succeed.
    """

    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)

    @property
    def message_format(self):
        return "Failed to parse run result: {error_type_and_message}"

    @property
    def message_parameters(self):
        error_type_and_message = None
        if self.inner_exception:
            error_type_and_message = f"({self.inner_exception.__class__.__name__}) {self.inner_exception}"

        return {
            "error_type_and_message": error_type_and_message,
        }


# endregion
