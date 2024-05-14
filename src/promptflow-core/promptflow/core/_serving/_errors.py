# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.exceptions import ErrorTarget, UserErrorException


class BadRequest(UserErrorException):
    pass


class JsonPayloadRequiredForMultipleInputFields(BadRequest):
    pass


class MissingRequiredFlowInput(BadRequest):
    pass


class InvalidFlowInitConfig(BadRequest):
    pass


class FlowConnectionError(UserErrorException):
    pass


class UnsupportedConnectionProvider(FlowConnectionError):
    def __init__(self, provider):
        super().__init__(
            message_format="Unsupported connection provider {provider}, " "supported are 'local' and typing.Callable.",
            provider=provider,
            target=ErrorTarget.FLOW_INVOKER,
        )


class MissingConnectionProvider(FlowConnectionError):
    pass


class InvalidConnectionData(FlowConnectionError):
    def __init__(self, connection_name):
        super().__init__(
            message_format="Invalid connection data detected while overriding connection {connection_name}.",
            connection_name=connection_name,
            target=ErrorTarget.FLOW_INVOKER,
        )


class UnexpectedConnectionProviderReturn(FlowConnectionError):
    pass


class AsyncGeneratorOutputNotSupported(UserErrorException):
    def __init__(self):
        super().__init__(
            "Flask engine does not support async generator output, please switch to use FastAPI engine.",
            target=ErrorTarget.SERVING_APP,
        )


class MultipleStreamOutputFieldsNotSupported(UserErrorException):
    def __init__(self):
        super().__init__(
            "Multiple stream output fields not supported.",
            target=ErrorTarget.SERVING_APP,
        )


class NotAcceptable(UserErrorException):
    def __init__(self, media_type, supported_media_types):
        super().__init__(
            message_format="Media type {media_type} in Accept header is not acceptable. "
            "Supported media type(s) - {supported_media_types}",
            media_type=media_type,
            supported_media_types=supported_media_types,
            target=ErrorTarget.SERVING_APP,
        )
