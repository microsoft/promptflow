# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import re
import io

from jinja2 import Template
from ruamel.yaml import YAML


def get_default_values(cls):
    signature = inspect.signature(cls.__init__)
    return {
        k: v.default
        for k, v in signature.parameters.items()
        if v.default is not inspect.Parameter.empty
    }


def generate_custom_strong_type_connection_spec(cls, package, package_version):
    connection_spec = {
        "connectionCategory": "CustomKeys",
        "flowValueType": "CustomConnection",
        "connectionType": cls.__name__,
        "ConnectionTypeDisplayName": cls.__name__,
        "configSpecs": [],
        "module": cls.__module__,
        "package": package,
        "package_version": package_version,
    }

    for k, typ in cls.__annotations__.items():
        spec = {
            "name": k,
            "displayName": k.replace("_", " ").title(),
            "configValueType": typ.__name__,
        }
        if hasattr(cls, k):
            spec["isOptional"] = getattr(cls, k, None) is not None
        else:
            spec["isOptional"] = False
        connection_spec["configSpecs"].append(spec)

    return connection_spec


def generate_custom_strong_type_connection_template(cls, connection_spec, package, package_version):
    connection_template_str = """
    name: "to_replace_with_connection_name"
    type: custom
    custom_type: {{ custom_type }}
    module: {{ module }}
    package: {{ package }}
    package_version: {{ package_version }}
    configs:
      {% for key, value in configs.items() %}
      {{ key }}: "{{ value -}}"{% endfor %}
    secrets:  # must-have{% for key, value in secrets.items() %}
      {{ key }}: "{{ value -}}"{% endfor %}
    """

    connection_template = Template(connection_template_str)

    # Extract configs and secrets
    configs = {}
    secrets = {}
    default_values = get_default_values(cls)
    for spec in connection_spec["configSpecs"]:
        if spec["configValueType"] == "Secret":
            secrets[spec["name"]] = "to_replace_with_" + spec["name"].replace("-", "_")
        else:
            configs[spec["name"]] = default_values[spec["name"]] \
                if spec["name"] in default_values.keys() else "to_replace_with_" + spec["name"].replace("-", "_")

    # Prepare data for template
    data = {
        "custom_type": cls.__name__,
        "module": cls.__module__,
        "package": package,
        "package_version": package_version,
        "configs": configs,
        "secrets": secrets
    }

    connection_template_with_data = connection_template.render(data)
    connection_template_with_comments = render_comments(
        connection_template_with_data,
        cls,
        secrets.keys(),
        configs.keys())

    return connection_template_with_comments


def render_comments(connection_template, cls, secrets, configs):
    if cls.__doc__ is not None:
        yaml = YAML()
        data = yaml.load(connection_template)
        comments_map = extract_comments_mapping(list(secrets) + list(configs), cls.__doc__)
        # Add comments for secret keys
        for key in secrets:
            if key in comments_map.keys():
                data['secrets'].yaml_add_eol_comment(comments_map[key] + '\n', key)

        # Add comments for config keys
        for key in configs:
            if key in comments_map.keys():
                data['configs'].yaml_add_eol_comment(comments_map[key] + '\n', key)

        # Dump data object back to string
        buf = io.StringIO()
        yaml.dump(data, buf)
        connection_template_with_comments = buf.getvalue()

        return connection_template_with_comments

    return connection_template


def extract_comments_mapping(keys, doc):
    comments_map = {}
    for key in keys:
        try:
            param_pattern = rf":param {key}: (.*)"
            key_description = ' '.join(re.findall(param_pattern, doc))
            type_pattern = rf":type {key}: (.*)"
            key_type = ' '.join(re.findall(type_pattern, doc)).rstrip('.')
            if key_type and key_description:
                comments_map[key] = ', '.join([key_type, key_description])
            elif key_type:
                comments_map[key] = key_type
            elif key_description:
                comments_map[key] = key_description
        except re.error:
            print("An error occurred when extract comments mapping.")

    return comments_map
