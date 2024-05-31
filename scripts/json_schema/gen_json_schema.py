# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# flake8: noqa

# This file is part of scripts\generate_json_schema.py in sdk-cli-v2, which is used to generate json schema
# To use this script, run `python <this_file>` in promptflow env,
# and the json schema will be generated in the same folder.


import argparse
from inspect import isclass, getmembers
import json
import sys

from azure.ai.ml._schema import ExperimentalField
from promptflow._sdk.schemas._base import YamlFileSchema
from promptflow._sdk.schemas._fields import UnionField
from marshmallow import Schema, fields, missing
from marshmallow.class_registry import get_class
from marshmallow_jsonschema import JSONSchema


class PatchedJSONSchema(JSONSchema):
    required = fields.Method("get_required")
    properties = fields.Method("get_properties")

    def __init__(self, *args, **kwargs):
        """Setup internal cache of nested fields, to prevent recursion.
        :param bool props_ordered: if `True` order of properties will be save as declare in class,
                                   else will using sorting, default is `False`.
                                   Note: For the marshmallow scheme, also need to enable
                                   ordering of fields too (via `class Meta`, attribute `ordered`).
        """
        self._nested_schema_classes = {}
        self.nested = kwargs.pop("nested", False)
        self.props_ordered = kwargs.pop("props_ordered", False)
        setattr(self.opts, "ordered", self.props_ordered)
        super().__init__(*args, **kwargs)

    # cspell: ignore pytype
    def _from_python_type(self, obj, field, pytype):
        metadata = field.metadata.get("metadata", {})
        metadata.update(field.metadata)
        # This is in the upcoming release of marshmallow-jsonschema, but not available yet
        if isinstance(field, fields.Dict):
            values = metadata.get("values", None) or field.value_field
            json_schema = {"title": field.attribute or field.data_key or field.name}
            json_schema["type"] = "object"
            if values:
                values.parent = field
            json_schema["additionalProperties"] = self._get_schema_for_field(obj, values) if values else {}
            return json_schema
        if isinstance(field, fields.Raw):
            json_schema = {"title": field.attribute or field.data_key or field.name}
            return json_schema

        return super()._from_python_type(obj, field, pytype)

    def _get_schema_for_field(self, obj, field):
        """Get schema and validators for field."""
        if hasattr(field, "_jsonschema_type_mapping"):
            schema = field._jsonschema_type_mapping()  # pylint: disable=protected-access
        elif "_jsonschema_type_mapping" in field.metadata:
            schema = field.metadata["_jsonschema_type_mapping"]
        else:
            if isinstance(field, UnionField):
                schema = self._get_schema_for_union_field(obj, field)
            elif isinstance(field, ExperimentalField):
                schema = self._get_schema_for_field(obj, field.experimental_field)
            elif isinstance(field, fields.Constant):
                schema = {"const": field.constant}
            else:
                schema = super()._get_schema_for_field(obj, field)
        if field.data_key:
            schema["title"] = field.data_key
        return schema

    def _get_schema_for_union_field(self, obj, field):
        has_yaml_option = False
        schemas = []
        for field_item in field._union_fields:  # pylint: disable=protected-access
            if isinstance(field_item, fields.Nested) and isinstance(field_item.schema, YamlFileSchema):
                has_yaml_option = True
            schemas.append(self._get_schema_for_field(obj, field_item))
        if has_yaml_option:
            schemas.append({"type": "string", "pattern": "^file:.*"})
        if field.allow_none:
            schemas.append({"type": "null"})
        if field.is_strict:
            schema = {"oneOf": schemas}
        else:
            schema = {"anyOf": schemas}
        # This happens in the super() call to get_schema, doing here to allow for adding
        # descriptions and other schema attributes from marshmallow metadata
        metadata = field.metadata.get("metadata", {})
        for md_key, md_val in metadata.items():
            if md_key in ("metadata", "name"):
                continue
            schema[md_key] = md_val
        return schema

    def _from_nested_schema(self, obj, field):
        """patch in context for nested field"""
        if isinstance(field.nested, (str, bytes)):
            nested = get_class(field.nested)
        else:
            nested = field.nested

        if isclass(nested) and issubclass(nested, Schema):
            only = field.only
            exclude = field.exclude
            context = getattr(field.parent, "context", {})
            field.nested = nested(only=only, exclude=exclude, context=context)
        return super()._from_nested_schema(obj, field)

    def get_properties(self, obj):
        """Fill out properties field."""
        properties = self.dict_class()

        if self.props_ordered:
            fields_items_sequence = obj.fields.items()
        else:
            fields_items_sequence = sorted(obj.fields.items())

        for _, field in fields_items_sequence:
            schema = self._get_schema_for_field(obj, field)
            properties[field.metadata.get("name") or field.data_key or field.name] = schema
        return properties

    def get_required(self, obj):
        """Fill out required field."""
        required = []

        for _, field in sorted(obj.fields.items()):
            if field.required:
                required.append(field.metadata.get("name") or field.data_key or field.name)

        return required or missing


from promptflow._sdk.schemas._connection import AzureOpenAIConnectionSchema, OpenAIConnectionSchema, \
QdrantConnectionSchema, CognitiveSearchConnectionSchema, SerpConnectionSchema, AzureContentSafetyConnectionSchema, \
FormRecognizerConnectionSchema, CustomConnectionSchema, WeaviateConnectionSchema, ServerlessConnectionSchema, \
CustomStrongTypeConnectionSchema, AzureAIServicesConnectionSchema
from promptflow._sdk.schemas._run import RunSchema
from promptflow._sdk.schemas._flow import FlowSchema, FlexFlowSchema


def dump_json(file_name, dct):
    with open(file_name, "w") as f:
        f.write(json.dumps(dct, indent=4))


if __name__ == "__main__":
    example_text = """Example usage:

python scripts/json_schema/gen_json_schema.py -o Run Flow # Generate Run.schema.json and Flow.schema.json
python scripts/json_schema/gen_json_schema.py -a # Generate all schema files
"""

    parser = argparse.ArgumentParser(epilog=example_text, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-o', '--output-file', nargs='+', help='Specify output file names, Run, Flow, etc.')
    parser.add_argument('-a', '--all', action='store_true', help='Generate all schema files')
    args = parser.parse_args()

    if args.all:
        args.output_file = ["Run", "Flow", "AzureOpenAIConnection", "OpenAIConnection", "QdrantConnection",
                            "CognitiveSearchConnection", "SerpConnection", "AzureContentSafetyConnection",
                            "FormRecognizerConnection", "CustomConnection", "WeaviateConnection", "ServerlessConnection",
                            "CustomStrongTypeConnection", "AzureAIServicesConnection"]

    # Special case for Flow and EagerFlow
    if "Flow" in args.output_file:
        cls_list = [FlowSchema, FlexFlowSchema]
        schema_list = []
        for cls in cls_list:
            target_schema = PatchedJSONSchema().dump(cls(context={"base_path": "./"}))
            # print(target_schema)
            file_name = cls.__name__
            file_name = file_name.replace("Schema", "")
            schema_list.append(target_schema["definitions"][cls.__name__])
            print(target_schema)
        schema = {
            "type": "object",
            "oneOf": schema_list
        }
        dump_json("Flow.schema.json", schema)
        # Dump another small case first letter one
        dump_json("flow.schema.json", schema)
        args.output_file.remove("Flow")

    prepared_schemas = {}

    # get all imported schemas
    for (name, cls) in getmembers(sys.modules[__name__]):
        if name.endswith("Schema"):
            prepared_schemas[name.split("Schema")[0]] = cls

    for item in args.output_file:
        item_cls = prepared_schemas.get(item, None)
        if item_cls is None:
            print(f"Schema not found for {item}")
        else:
            target_schema = PatchedJSONSchema().dump(item_cls(context={"base_path": "./"}))
            dump_json(f"{item}.schema.json", target_schema)
            # Dump another small case first letter one
            item = item[0].lower() + item[1:]
            dump_json(f"{item}.schema.json", target_schema)
