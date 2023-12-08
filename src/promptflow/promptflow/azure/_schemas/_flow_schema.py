# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
from pathlib import Path

from azure.ai.ml._schema import UnionField, YamlFileSchema
from azure.ai.ml._schema.core.fields import LocalPathField
from marshmallow import fields, post_load

from promptflow._utils.logger_utils import LoggerFactory

module_logger = LoggerFactory.get_logger(__name__)


class FlowSchema(YamlFileSchema):
    name = fields.Str(attribute="name")
    id = fields.Str(attribute="id")
    description = fields.Str(attribute="description")
    tags = fields.Dict(keys=fields.Str, attribute="tags")
    path = UnionField(
        [
            LocalPathField(),
            fields.Str(),
        ],
    )
    display_name = fields.Str(attribute="display_name")
    type = fields.Str(attribute="type")
    properties = fields.Dict(keys=fields.Str, attribute="properties")

    @post_load
    def update_properties(self, dct, **kwargs):
        folder = Path(self.context["base_path"])

        flow_type = dct.get("type")
        if flow_type:
            mapping = {
                "standard": "default",
                "evaluate": "evaluation",
            }
            dct["type"] = mapping[flow_type]

        properties = dct.get("properties")
        if properties and "promptflow.batch_inputs" in properties:
            input_path = properties["promptflow.batch_inputs"]
            samples_file = folder / input_path
            if samples_file.exists():
                with open(samples_file, "r", encoding="utf-8") as fp:
                    properties["promptflow.batch_inputs"] = json.loads(fp.read())

        return dct
