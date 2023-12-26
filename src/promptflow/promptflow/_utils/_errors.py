from promptflow.exceptions import UserErrorException, ValidationException


class InvalidImageInput(ValidationException):
    pass


class LoadMultimediaDataError(UserErrorException):
    pass
