# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# pylint: disable=protected-access

import json
import typing

from marshmallow import Schema, ValidationError

from promptflow._utils.logger_utils import LoggerFactory

from .core import MutableValidationResult, ValidationResultBuilder

module_logger = LoggerFactory.get_logger(__name__)


class SchemaValidatableMixin:
    """The mixin class for schema validation."""

    @classmethod
    def _create_empty_validation_result(cls) -> MutableValidationResult:
        """Simply create an empty validation result

        To reduce _ValidationResultBuilder importing, which is a private class.

        :return: An empty validation result
        :rtype: MutableValidationResult
        """
        return ValidationResultBuilder.success()

    @classmethod
    def _load_with_schema(cls, data, *, context, raise_original_exception=False, **kwargs):
        schema = cls._create_schema_for_validation(context=context)

        try:
            return schema.load(data, **kwargs)
        except ValidationError as e:
            if raise_original_exception:
                raise e
            msg = "Trying to load data with schema failed. Data:\n%s\nError: %s" % (
                json.dumps(data, indent=4) if isinstance(data, dict) else data,
                json.dumps(e.messages, indent=4),
            )
            raise cls._create_validation_error(
                message=msg,
                no_personal_data_message=str(e),
            ) from e

    @classmethod
    # pylint: disable-next=docstring-missing-param
    def _create_schema_for_validation(cls, context) -> Schema:
        """Create a schema of the resource with specific context. Should be overridden by subclass.

        :return: The schema of the resource.
        :rtype: Schema.
        """
        raise NotImplementedError()

    def _default_context(self) -> dict:
        """Get the default context for schema validation. Should be overridden by subclass.

        :return: The default context for schema validation
        :rtype: dict
        """
        raise NotImplementedError()

    @property
    def _schema_for_validation(self) -> Schema:
        """Return the schema of this Resource with default context. Do not override this method.
        Override _create_schema_for_validation instead.

        :return: The schema of the resource.
        :rtype: Schema.
        """
        return self._create_schema_for_validation(context=self._default_context())

    def _dump_for_validation(self) -> typing.Dict:
        """Convert the resource to a dictionary.

        :return: Converted dictionary
        :rtype: typing.Dict
        """
        return self._schema_for_validation.dump(self)

    @classmethod
    def _create_validation_error(cls, message: str, no_personal_data_message: str) -> Exception:
        """The function to create the validation exception to raise in _try_raise and _validate when
        raise_error is True.

        Should be overridden by subclass.

        :param message: The error message containing detailed information
        :type message: str
        :param no_personal_data_message: The error message without personal data
        :type no_personal_data_message: str
        :return: The validation exception to raise
        :rtype: Exception
        """
        raise NotImplementedError()

    @classmethod
    def _try_raise(
        cls, validation_result: MutableValidationResult, *, raise_error: bool = True
    ) -> MutableValidationResult:
        return validation_result.try_raise(raise_error=raise_error, error_func=cls._create_validation_error)

    def _validate(self, raise_error=False) -> MutableValidationResult:
        """Validate the resource. If raise_error is True, raise ValidationError if validation fails and log warnings if
        applicable; Else, return the validation result.

        :param raise_error: Whether to raise ValidationError if validation fails.
        :type raise_error: bool
        :return: The validation result
        :rtype: MutableValidationResult
        """
        result = self.__schema_validate()
        result.merge_with(self._customized_validate())
        return self._try_raise(result, raise_error=raise_error)

    def _customized_validate(self) -> MutableValidationResult:
        """Validate the resource with customized logic.

        Override this method to add customized validation logic.

        :return: The customized validation result
        :rtype: MutableValidationResult
        """
        return self._create_empty_validation_result()

    @classmethod
    def _get_skip_fields_in_schema_validation(
        cls,
    ) -> typing.List[str]:
        """Get the fields that should be skipped in schema validation.

        Override this method to add customized validation logic.

        :return: The fields to skip in schema validation
        :rtype: typing.List[str]
        """
        return []

    def __schema_validate(self) -> MutableValidationResult:
        """Validate the resource with the schema.

        :return: The validation result
        :rtype: MutableValidationResult
        """
        data = self._dump_for_validation()
        messages = self._schema_for_validation.validate(data)
        for skip_field in self._get_skip_fields_in_schema_validation():
            if skip_field in messages:
                del messages[skip_field]
        return ValidationResultBuilder.from_validation_messages(messages, data=data)
