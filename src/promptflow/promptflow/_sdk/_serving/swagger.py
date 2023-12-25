# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging

from promptflow.contracts.flow import Flow, FlowInputDefinition, FlowOutputDefinition
from promptflow.contracts.tool import ValueType

type_mapping = {
    ValueType.INT: "integer",
    ValueType.DOUBLE: "number",
    ValueType.BOOL: "boolean",
    ValueType.STRING: "string",
    ValueType.LIST: "array",
    ValueType.OBJECT: "object",
    ValueType.IMAGE: "object",  # Dump as object as portal test page can't handle image now
}


def generate_input_field_schema(input: FlowInputDefinition) -> dict:
    field_schema = {"type": type_mapping[input.type]}
    if input.description:
        field_schema["description"] = input.description
    if input.default:
        field_schema["default"] = input.default
    if input.type == ValueType.OBJECT:
        field_schema["additionalProperties"] = {}
    if input.type == ValueType.LIST:
        field_schema["items"] = {"type": "object", "additionalProperties": {}}
    return field_schema


def generate_output_field_schema(output: FlowOutputDefinition) -> dict:
    field_schema = {"type": type_mapping[output.type]}
    if output.description:
        field_schema["description"] = output.description
    if output.type == ValueType.OBJECT:
        field_schema["additionalProperties"] = {}
    if output.type == ValueType.LIST:
        field_schema["items"] = {"type": "object", "additionalProperties": {}}
    return field_schema


def generate_swagger(flow: Flow, samples, outputs_to_remove: list) -> dict:
    """convert a flow to swagger object."""
    swagger = {"openapi": "3.0.0"}
    swagger["info"] = {
        "title": f"Promptflow[{flow.name}] API",
        "version": "1.0.0",
        "x-flow-name": str(flow.name),
    }

    swagger["components"] = {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
            }
        }
    }

    swagger["security"] = [{"bearerAuth": []}]

    input_schema = {"type": "object"}
    request_body_required = False
    if len(flow.inputs) > 0:
        input_schema["properties"] = {}
        input_schema["required"] = []
        request_body_required = True
        for name, input in flow.inputs.items():
            if input.is_chat_input:
                swagger["info"]["x-chat-input"] = name
                swagger["info"]["x-flow-type"] = "chat"
            if input.is_chat_history:
                swagger["info"]["x-chat-history"] = name
            input_schema["properties"][name] = generate_input_field_schema(input)
            input_schema["required"].append(name)

    output_schema = {"type": "object"}
    if len(flow.outputs) > 0:
        output_schema["properties"] = {}
        for name, output in flow.outputs.items():
            # skip evaluation only outputs in swagger
            # TODO remove this if sdk removed this evaluation_only field
            if output.evaluation_only:
                continue
            if output.is_chat_output:
                swagger["info"]["x-chat-output"] = name
            if outputs_to_remove and name in outputs_to_remove:
                continue
            output_schema["properties"][name] = generate_output_field_schema(output)

    example = {}
    if samples:
        if isinstance(samples, list):
            example = samples[0]
        else:
            logging.warning("samples should be a list of dict, but got %s, skipped.", type(samples))

    swagger["paths"] = {
        "/score": {
            "post": {
                "summary": f"run promptflow: {flow.name} with an given input",
                "requestBody": {
                    "description": "promptflow input data",
                    "required": request_body_required,
                    "content": {
                        "application/json": {
                            "schema": input_schema,
                            "example": example,  # need to check this based on the sample data
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "successful operation",
                        "content": {
                            "application/json": {
                                "schema": output_schema,
                            }
                        },
                    },
                    "400": {
                        "description": "Invalid input",
                    },
                    "default": {
                        "description": "unexpected error",
                    },
                },
            }
        }
    }
    return swagger
