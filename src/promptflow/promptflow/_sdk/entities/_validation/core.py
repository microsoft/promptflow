# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# pylint: disable=protected-access

import copy
import json
import os.path
import typing
from pathlib import Path
from typing import Dict, List, Optional

import pydash
import strictyaml
from marshmallow import ValidationError

from promptflow._utils.logger_utils import get_cli_sdk_logger

logger = get_cli_sdk_logger()


class _ValidationStatus:
    """Validation status class.

    Validation status is used to indicate the status of an validation result. It can be one of the following values:
    Succeeded, Failed.
    """

    SUCCEEDED = "Succeeded"
    """Succeeded."""
    FAILED = "Failed"
    """Failed."""


class Diagnostic(object):
    """Represents a diagnostic of an asset validation error with the location info."""

    def __init__(self, yaml_path: str, message: str, error_code: str, **kwargs) -> None:
        """Init Diagnostic.

        :keyword yaml_path: A dash path from root to the target element of the diagnostic.
        :paramtype yaml_path: str
        :keyword message: Error message of diagnostic.
        :paramtype message: str
        :keyword error_code: Error code of diagnostic.
        :paramtype error_code: str
        """
        self.yaml_path = yaml_path
        self.message = message
        self.error_code = error_code
        self.local_path, self.value = None, None
        self._key = kwargs.pop("key", "yaml_path")
        # Set extra info to attribute
        for k, v in kwargs.items():
            if not k.startswith("_"):
                setattr(self, k, v)

    def __repr__(self) -> str:
        """The asset friendly name and error message.

        :return: The formatted diagnostic
        :rtype: str
        """
        return "{}: {}".format(getattr(self, self._key), self.message)

    @classmethod
    def create_instance(
        cls,
        yaml_path: str,
        message: Optional[str] = None,
        error_code: Optional[str] = None,
        **kwargs,
    ):
        """Create a diagnostic instance.

        :param yaml_path: A dash path from root to the target element of the diagnostic.
        :type yaml_path: str
        :param message: Error message of diagnostic.
        :type message: str
        :param error_code: Error code of diagnostic.
        :type error_code: str
        :return: The created instance
        :rtype: Diagnostic
        """
        return cls(
            yaml_path=yaml_path,
            message=message,
            error_code=error_code,
            **kwargs,
        )


class ValidationResult(object):
    """Represents the result of validation.

    This class is used to organize and parse diagnostics from both client & server side before expose them. The result
    is immutable.
    """

    def __init__(self) -> None:
        self._target_obj = None
        self._errors = []
        self._warnings = []
        self._kwargs = {}

    def _set_extra_info(self, key, value):
        self._kwargs[key] = value

    def _get_extra_info(self, key, default=None):
        return self._kwargs.get(key, default)

    @property
    def error_messages(self) -> Dict:
        """
        Return all messages of errors in the validation result.

        :return: A dictionary of error messages. The key is the yaml path of the error, and the value is the error
            message.
        :rtype: dict
        """
        messages = {}
        for diagnostic in self._errors:
            message_key = getattr(diagnostic, diagnostic._key)
            if message_key not in messages:
                messages[message_key] = diagnostic.message
            else:
                messages[message_key] += "; " + diagnostic.message
        return messages

    @property
    def passed(self) -> bool:
        """Returns boolean indicating whether any errors were found.

        :return: True if the validation passed, False otherwise.
        :rtype: bool
        """
        return not self._errors

    def _to_dict(self) -> typing.Dict[str, typing.Any]:
        result = {
            "result": _ValidationStatus.SUCCEEDED if self.passed else _ValidationStatus.FAILED,
        }
        result.update(self._kwargs)
        for diagnostic_type, diagnostics in [
            ("errors", self._errors),
            ("warnings", self._warnings),
        ]:
            messages = []
            for diagnostic in diagnostics:
                message = {
                    "message": diagnostic.message,
                    "path": diagnostic.yaml_path,
                    "value": pydash.get(self._target_obj, diagnostic.yaml_path, diagnostic.value),
                }
                if diagnostic.local_path:
                    message["location"] = str(diagnostic.local_path)
                for attr in dir(diagnostic):
                    if attr not in message and not attr.startswith("_") and not callable(getattr(diagnostic, attr)):
                        message[attr] = getattr(diagnostic, attr)
                message = {k: v for k, v in message.items() if v is not None}
                messages.append(message)
            if messages:
                result[diagnostic_type] = messages
        return result

    def __repr__(self) -> str:
        """Get the string representation of the validation result.

        :return: The string representation
        :rtype: str
        """
        return json.dumps(self._to_dict(), indent=2)


class MutableValidationResult(ValidationResult):
    """Used by the client side to construct a validation result.

    The result is mutable and should not be exposed to the user.
    """

    def __init__(self, target_obj: Optional[typing.Dict[str, typing.Any]] = None):
        super().__init__()
        self._target_obj = target_obj

    def merge_with(
        self,
        target: ValidationResult,
        field_name: Optional[str] = None,
        condition_skip: Optional[typing.Callable] = None,
        overwrite: bool = False,
    ):
        """Merge errors & warnings in another validation results into current one.

        Will update current validation result.
        If field_name is not None, then yaml_path in the other validation result will be updated accordingly.
        * => field_name, a.b => field_name.a.b e.g.. If None, then no update.

        :param target: Validation result to merge.
        :type target: ValidationResult
        :param field_name: The base field name for the target to merge.
        :type field_name: str
        :param condition_skip: A function to determine whether to skip the merge of a diagnostic in the target.
        :type condition_skip: typing.Callable
        :param overwrite: Whether to overwrite the current validation result. If False, all diagnostics will be kept;
            if True, current diagnostics with the same yaml_path will be dropped.
        :type overwrite: bool
        :return: The current validation result.
        :rtype: MutableValidationResult
        """
        for source_diagnostics, target_diagnostics in [
            (target._errors, self._errors),
            (target._warnings, self._warnings),
        ]:
            if overwrite:
                keys_to_remove = set(map(lambda x: x.yaml_path, source_diagnostics))
                target_diagnostics[:] = [
                    diagnostic for diagnostic in target_diagnostics if diagnostic.yaml_path not in keys_to_remove
                ]
            for diagnostic in source_diagnostics:
                if condition_skip and condition_skip(diagnostic):
                    continue
                new_diagnostic = copy.deepcopy(diagnostic)
                if field_name:
                    if new_diagnostic.yaml_path == "*":
                        new_diagnostic.yaml_path = field_name
                    else:
                        new_diagnostic.yaml_path = field_name + "." + new_diagnostic.yaml_path
                target_diagnostics.append(new_diagnostic)
        return self

    def try_raise(
        self,
        raise_error: bool = True,
        *,
        error_func: typing.Callable[[str, str], Exception] = None,
    ) -> "MutableValidationResult":
        """Try to raise an error from the validation result.

        If the validation is passed or raise_error is False, this method
        will return the validation result.

        :param raise_error: Whether to raise the error.
        :type raise_error: bool
        :keyword error_func: A function to create the error. If None, a marshmallow.ValidationError will be created.
                             The first parameter of the function is the string representation of the validation result,
                             and the second parameter is the error message without personal data.
        :type error_func: typing.Callable[[str, str], Exception]
        :return: The current validation result.
        :rtype: MutableValidationResult
        """
        # pylint: disable=logging-not-lazy
        if raise_error is False:
            return self

        if self._warnings:
            logger.warning("Schema validation warnings: %s" % str(self._warnings))

        if not self.passed:
            if error_func is None:

                def error_func(msg, _):
                    return ValidationError(message=msg)

            raise error_func(
                self.__repr__(),
                f"Schema validation failed: {self.error_messages}",
            )
        return self

    def append_error(
        self,
        yaml_path: str = "*",
        message: Optional[str] = None,
        error_code: Optional[str] = None,
        **kwargs,
    ):
        """Append an error to the validation result.

        :param yaml_path: The yaml path of the error.
        :type yaml_path: str
        :param message: The message of the error.
        :type message: str
        :param error_code: The error code of the error.
        :type error_code: str
        :return: The current validation result.
        :rtype: MutableValidationResult
        """
        self._errors.append(
            Diagnostic.create_instance(
                yaml_path=yaml_path,
                message=message,
                error_code=error_code,
                **kwargs,
            )
        )
        return self

    def resolve_location_for_diagnostics(self, source_path: str, resolve_value: bool = False):
        """Resolve location/value for diagnostics based on the source path where the validatable object is loaded.

        Location includes local path of the exact file (can be different from the source path) & line number of the
        invalid field. Value of a diagnostic is resolved from the validatable object in transfering to a dict by
        default; however, when the validatable object is not available for the validation result, validation result is
        created from marshmallow.ValidationError.messages e.g., it can be resolved from the source path.

        :param source_path: The path of the source file.
        :type source_path: str
        :param resolve_value: Whether to resolve the value of the invalid field from source file.
        :type resolve_value: bool
        """
        resolver = _YamlLocationResolver(source_path)
        for diagnostic in self._errors + self._warnings:
            diagnostic.local_path, value = resolver.resolve(diagnostic.yaml_path)
            if value is not None and resolve_value:
                diagnostic.value = value

    def append_warning(
        self,
        yaml_path: str = "*",
        message: Optional[str] = None,
        error_code: Optional[str] = None,
        **kwargs,
    ):
        """Append a warning to the validation result.

        :param yaml_path: The yaml path of the warning.
        :type yaml_path: str
        :param message: The message of the warning.
        :type message: str
        :param error_code: The error code of the warning.
        :type error_code: str
        :return: The current validation result.
        :rtype: MutableValidationResult
        """
        self._warnings.append(
            Diagnostic.create_instance(
                yaml_path=yaml_path,
                message=message,
                error_code=error_code,
                **kwargs,
            )
        )
        return self


class ValidationResultBuilder:
    """A helper class to create a validation result."""

    UNKNOWN_MESSAGE = "Unknown field."

    def __init__(self):
        pass

    @classmethod
    def success(cls) -> MutableValidationResult:
        """Create a validation result with success status.

        :return: A validation result
        :rtype: MutableValidationResult
        """
        return MutableValidationResult()

    @classmethod
    def from_single_message(
        cls, singular_error_message: Optional[str] = None, yaml_path: str = "*", data: Optional[dict] = None
    ):
        """Create a validation result with only 1 diagnostic.

        :param singular_error_message: diagnostic.message.
        :type singular_error_message: Optional[str]
        :param yaml_path: diagnostic.yaml_path.
        :type yaml_path: str
        :param data: serializedvalidation target.
        :type data: Optional[Dict]
        :return: The validation result
        :rtype: MutableValidationResult
        """
        obj = MutableValidationResult(target_obj=data)
        if singular_error_message:
            obj.append_error(message=singular_error_message, yaml_path=yaml_path)
        return obj

    @classmethod
    def from_validation_error(
        cls, error: ValidationError, *, source_path: Optional[str] = None, error_on_unknown_field=False
    ) -> MutableValidationResult:
        """Create a validation result from a ValidationError, which will be raised in marshmallow.Schema.load. Please
        use this function only for exception in loading file.

        :param error: ValidationError raised by marshmallow.Schema.load.
        :type error: ValidationError
        :keyword error_on_unknown_field: whether to raise error if there are unknown field diagnostics.
        :paramtype error_on_unknown_field: bool
        :return: The validation result
        :rtype: MutableValidationResult
        """
        obj = cls.from_validation_messages(
            error.messages, data=error.data, error_on_unknown_field=error_on_unknown_field
        )
        if source_path:
            obj.resolve_location_for_diagnostics(source_path, resolve_value=True)
        return obj

    @classmethod
    def from_validation_messages(
        cls, errors: typing.Dict, data: typing.Dict, *, error_on_unknown_field: bool = False
    ) -> MutableValidationResult:
        """Create a validation result from error messages, which will be returned by marshmallow.Schema.validate.

        :param errors: error message returned by marshmallow.Schema.validate.
        :type errors: dict
        :param data: serialized data to validate
        :type data: dict
        :keyword error_on_unknown_field: whether to raise error if there are unknown field diagnostics.
        :paramtype error_on_unknown_field: bool
        :return: The validation result
        :rtype: MutableValidationResult
        """
        instance = MutableValidationResult(target_obj=data)
        errors = copy.deepcopy(errors)
        cls._from_validation_messages_recursively(errors, [], instance, error_on_unknown_field=error_on_unknown_field)
        return instance

    @classmethod
    def _from_validation_messages_recursively(
        cls,
        errors: typing.Union[typing.Dict, typing.List, str],
        path_stack: typing.List[str],
        instance: MutableValidationResult,
        error_on_unknown_field: bool,
    ):
        cur_path = ".".join(path_stack) if path_stack else "*"
        # single error message
        if isinstance(errors, dict) and "_schema" in errors:
            instance.append_error(
                message=";".join(errors["_schema"]),
                yaml_path=cur_path,
            )
        # errors on attributes
        elif isinstance(errors, dict):
            for field, msgs in errors.items():
                # fields.Dict
                if field in ["key", "value"]:
                    cls._from_validation_messages_recursively(msgs, path_stack, instance, error_on_unknown_field)
                else:
                    # Todo: Add hack logic here to deal with error message in nested TypeSensitiveUnionField in
                    #  DataTransfer: will be a nested dict with None field as dictionary key.
                    #  open a item to track: https://msdata.visualstudio.com/Vienna/_workitems/edit/2244262/
                    if field is None:
                        cls._from_validation_messages_recursively(msgs, path_stack, instance, error_on_unknown_field)
                    else:
                        path_stack.append(field)
                        cls._from_validation_messages_recursively(msgs, path_stack, instance, error_on_unknown_field)
                        path_stack.pop()

        # detailed error message
        elif isinstance(errors, list) and all(isinstance(msg, str) for msg in errors):
            if cls.UNKNOWN_MESSAGE in errors and not error_on_unknown_field:
                # Unknown field is not a real error, so we should remove it and append a warning.
                errors.remove(cls.UNKNOWN_MESSAGE)
                instance.append_warning(message=cls.UNKNOWN_MESSAGE, yaml_path=cur_path)
            if errors:
                instance.append_error(message=";".join(errors), yaml_path=cur_path)
        # union field
        elif isinstance(errors, list):

            def msg2str(msg):
                if isinstance(msg, str):
                    return msg
                if isinstance(msg, dict) and len(msg) == 1 and "_schema" in msg and len(msg["_schema"]) == 1:
                    return msg["_schema"][0]

                return str(msg)

            instance.append_error(message="; ".join([msg2str(x) for x in errors]), yaml_path=cur_path)
        # unknown error
        else:
            instance.append_error(message=str(errors), yaml_path=cur_path)


class _YamlLocationResolver:
    def __init__(self, source_path):
        self._source_path = source_path

    def resolve(self, yaml_path, source_path=None):
        """Resolve the location & value of a yaml path starting from source_path.

        :param yaml_path: yaml path.
        :type yaml_path: str
        :param source_path: source path.
        :type source_path: str
        :return: the location & value of the yaml path based on source_path.
        :rtype: Tuple[str, str]
        """
        source_path = source_path or self._source_path
        if source_path is None or not os.path.isfile(source_path):
            return None, None
        if yaml_path is None or yaml_path == "*":
            return source_path, None

        attrs = yaml_path.split(".")
        attrs.reverse()

        return self._resolve_recursively(attrs, Path(source_path))

    def _resolve_recursively(self, attrs: List[str], source_path: Path):
        with open(source_path, encoding="utf-8") as f:
            try:
                loaded_yaml = strictyaml.load(f.read())
            except Exception as e:  # pylint: disable=broad-except
                msg = "Can't load source file %s as a strict yaml:\n%s" % (source_path, str(e))
                logger.debug(msg)
                return None, None

        while attrs:
            attr = attrs[-1]
            if loaded_yaml.is_mapping() and attr in loaded_yaml:
                loaded_yaml = loaded_yaml.get(attr)
                attrs.pop()
            elif loaded_yaml.is_sequence() and attr.isdigit() and 0 <= int(attr) < len(loaded_yaml):
                loaded_yaml = loaded_yaml[int(attr)]
                attrs.pop()
            else:
                try:
                    # if current object is a path of a valid yaml file, try to resolve location in new source file
                    next_path = Path(loaded_yaml.value)
                    if not next_path.is_absolute():
                        next_path = source_path.parent / next_path
                    if next_path.is_file():
                        return self._resolve_recursively(attrs, source_path=next_path)
                except OSError:
                    pass
                except TypeError:
                    pass
                # if not, return current section
                break
        return (
            f"{source_path.resolve().absolute()}#line {loaded_yaml.start_line}",
            None if attrs else loaded_yaml.value,
        )
