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
