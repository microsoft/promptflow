# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import copy
import typing
from pathlib import Path

from marshmallow import fields
from marshmallow.exceptions import FieldInstanceResolutionError, ValidationError
from marshmallow.fields import _T, Field, Nested
from marshmallow.utils import RAISE, resolve_field_instance

from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY
from promptflow._sdk.schemas._base import PathAwareSchema
from promptflow._utils.logger_utils import LoggerFactory

# pylint: disable=unused-argument,no-self-use,protected-access

module_logger = LoggerFactory.get_logger(__name__)


class StringTransformedEnum(Field):
    def __init__(self, **kwargs):
        # pop marshmallow unknown args to avoid warnings
        self.allowed_values = kwargs.pop("allowed_values", None)
        self.casing_transform = kwargs.pop("casing_transform", lambda x: x.lower())
        self.pass_original = kwargs.pop("pass_original", False)
        super().__init__(**kwargs)
        if isinstance(self.allowed_values, str):
            self.allowed_values = [self.allowed_values]
        self.allowed_values = [self.casing_transform(x) for x in self.allowed_values]

    def _jsonschema_type_mapping(self):
        schema = {"type": "string", "enum": self.allowed_values}
        if self.name is not None:
            schema["title"] = self.name
        if self.dump_only:
            schema["readonly"] = True
        return schema

    def _serialize(self, value, attr, obj, **kwargs):
        if not value:
            return
        if isinstance(value, str) and self.casing_transform(value) in self.allowed_values:
            return value if self.pass_original else self.casing_transform(value)
        raise ValidationError(f"Value {value!r} passed is not in set {self.allowed_values}")

    def _deserialize(self, value, attr, data, **kwargs):
        if isinstance(value, str) and self.casing_transform(value) in self.allowed_values:
            return value if self.pass_original else self.casing_transform(value)
        raise ValidationError(f"Value {value!r} passed is not in set {self.allowed_values}")


class LocalPathField(fields.Str):
    """A field that validates that the input is a local path.

    Can only be used as fields of PathAwareSchema.
    """

    default_error_messages = {
        "invalid_path": "The filename, directory name, or volume label syntax is incorrect.",
        "path_not_exist": "Can't find {allow_type} in resolved absolute path: {path}.",
    }

    def __init__(self, allow_dir=True, allow_file=True, check_exists=True, **kwargs):
        self._allow_dir = allow_dir
        self._allow_file = allow_file
        self._check_exists = check_exists
        self._pattern = kwargs.get("pattern", None)
        super().__init__(**kwargs)

    def _resolve_path(self, value) -> Path:
        """Resolve path to absolute path based on base_path in context.

        Will resolve the path if it's already an absolute path.
        """
        try:
            result = Path(value)
            base_path = Path(self.context[BASE_PATH_CONTEXT_KEY])
            if not result.is_absolute():
                result = base_path / result

            # for non-path string like "azureml:/xxx", OSError can be raised in either
            # resolve() or is_dir() or is_file()
            result = result.resolve()
            if not self._check_exists:
                return result
            if (self._allow_dir and result.is_dir()) or (self._allow_file and result.is_file()):
                return result
        except OSError:
            raise self.make_error("invalid_path")
        raise self.make_error("path_not_exist", path=result.as_posix(), allow_type=self.allowed_path_type)

    @property
    def allowed_path_type(self) -> str:
        if self._allow_dir and self._allow_file:
            return "directory or file"
        if self._allow_dir:
            return "directory"
        return "file"

    def _validate(self, value):
        # inherited validations like required, allow_none, etc.
        super(LocalPathField, self)._validate(value)

        if value is None:
            return
        self._resolve_path(value)

    def _serialize(self, value, attr, obj, **kwargs) -> typing.Optional[str]:
        # do not block serializing None even if required or not allow_none.
        if value is None:
            return None
        # always dump path as absolute path in string as base_path will be dropped after serialization
        return super(LocalPathField, self)._serialize(self._resolve_path(value).as_posix(), attr, obj, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        # resolve to absolute path
        if value is None:
            return None
        return super()._deserialize(self._resolve_path(value).as_posix(), attr, data, **kwargs)


# Note: Currently contains a bug where the order in which fields are inputted can potentially cause a bug
# Example, the first line below works, but the second one fails upon calling load_from_dict
# with the error " AttributeError: 'list' object has no attribute 'get'"
# inputs = UnionField([fields.List(NestedField(DataSchema)), NestedField(DataSchema)])
# inputs = UnionField([NestedField(DataSchema), fields.List(NestedField(DataSchema))])
class UnionField(fields.Field):
    def __init__(self, union_fields: typing.List[fields.Field], is_strict=False, **kwargs):
        super().__init__(**kwargs)
        try:
            # add the validation and make sure union_fields must be subclasses or instances of
            # marshmallow.base.FieldABC
            self._union_fields = [resolve_field_instance(cls_or_instance) for cls_or_instance in union_fields]
            # TODO: make serialization/de-serialization work in the same way as json schema when is_strict is True
            self.is_strict = is_strict  # S\When True, combine fields with oneOf instead of anyOf at schema generation
        except FieldInstanceResolutionError as error:
            raise ValueError(
                'Elements of "union_fields" must be subclasses or ' "instances of marshmallow.base.FieldABC."
            ) from error

    @property
    def union_fields(self):
        return iter(self._union_fields)

    def insert_union_field(self, field):
        self._union_fields.insert(0, field)

    # This sets the parent for the schema and also handles nesting.
    def _bind_to_schema(self, field_name, schema):
        super()._bind_to_schema(field_name, schema)
        self._union_fields = self._create_bind_fields(self._union_fields, field_name)

    def _create_bind_fields(self, _fields, field_name):
        new_union_fields = []
        for field in _fields:
            field = copy.deepcopy(field)
            field._bind_to_schema(field_name, self)
            new_union_fields.append(field)
        return new_union_fields

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        errors = []
        for field in self._union_fields:
            try:
                return field._serialize(value, attr, obj, **kwargs)

            except ValidationError as e:
                errors.extend(e.messages)
            except (TypeError, ValueError, AttributeError) as e:
                errors.extend([str(e)])
        raise ValidationError(message=errors, field_name=attr)

    def _deserialize(self, value, attr, data, **kwargs):
        errors = []
        for schema in self._union_fields:
            try:
                return schema.deserialize(value, attr, data, **kwargs)
            except ValidationError as e:
                errors.append(e.normalized_messages())
            except (FileNotFoundError, TypeError) as e:
                errors.append([str(e)])
            finally:
                # Revert base path to original path when job schema fail to deserialize job. For example, when load
                # parallel job with component file reference starting with FILE prefix, maybe first CommandSchema will
                # load component yaml according to AnonymousCommandComponentSchema, and YamlFileSchema will update base
                # path. When CommandSchema fail to load, then Parallelschema will load component yaml according to
                # AnonymousParallelComponentSchema, but base path now is incorrect, and will raise path not found error
                # when load component yaml file.
                if (
                    hasattr(schema, "name")
                    and schema.name == "jobs"
                    and hasattr(schema, "schema")
                    and isinstance(schema.schema, PathAwareSchema)
                ):
                    # use old base path to recover original base path
                    schema.schema.context[BASE_PATH_CONTEXT_KEY] = schema.schema.old_base_path
                    # recover base path of parent schema
                    schema.context[BASE_PATH_CONTEXT_KEY] = schema.schema.context[BASE_PATH_CONTEXT_KEY]
        raise ValidationError(errors, field_name=attr)


class NestedField(Nested):
    """anticipates the default coming in next marshmallow version, unknown=True."""

    def __init__(self, *args, **kwargs):
        if kwargs.get("unknown") is None:
            kwargs["unknown"] = RAISE
        super().__init__(*args, **kwargs)


class DumpableIntegerField(fields.Integer):
    """An int field that cannot serialize other type of values to int if self.strict."""

    def _serialize(self, value, attr, obj, **kwargs) -> typing.Optional[typing.Union[str, _T]]:
        if self.strict and not isinstance(value, int):
            # this implementation can serialize bool to bool
            raise self.make_error("invalid", input=value)
        return super()._serialize(value, attr, obj, **kwargs)


class DumpableFloatField(fields.Float):
    """A float field that cannot serialize other type of values to float if self.strict."""

    def __init__(
        self,
        *,
        strict: bool = False,
        allow_nan: bool = False,
        as_string: bool = False,
        **kwargs,
    ):
        self.strict = strict
        super().__init__(allow_nan=allow_nan, as_string=as_string, **kwargs)

    def _validated(self, value):
        if self.strict and not isinstance(value, float):
            raise self.make_error("invalid", input=value)
        return super()._validated(value)

    def _serialize(self, value, attr, obj, **kwargs) -> typing.Optional[typing.Union[str, _T]]:
        return super()._serialize(self._validated(value), attr, obj, **kwargs)


def PrimitiveValueField(**kwargs):
    """Function to return a union field for primitive value.

    :return: The primitive value field
    :rtype: Field
    """
    return UnionField(
        [
            # Note: order matters here - to make sure value parsed correctly.
            # By default, when strict is false, marshmallow downcasts float to int.
            # Setting it to true will throw a validation error when loading a float to int.
            # https://github.com/marshmallow-code/marshmallow/pull/755
            # Use DumpableIntegerField to make sure there will be validation error when
            # loading/dumping a float to int.
            # note that this field can serialize bool instance but cannot deserialize bool instance.
            DumpableIntegerField(strict=True),
            # Use DumpableFloatField with strict of True to avoid '1'(str) serialized to 1.0(float)
            DumpableFloatField(strict=True),
            # put string schema after Int and Float to make sure they won't dump to string
            fields.Str(),
            # fields.Bool comes last since it'll parse anything non-falsy to True
            fields.Bool(),
        ],
        **kwargs,
    )
