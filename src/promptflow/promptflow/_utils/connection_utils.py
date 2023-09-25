# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import re
import io

from jinja2 import Template
from ruamel.yaml import YAML


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
    name: <connection-name>
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
    for spec in connection_spec["configSpecs"]:
        if spec["configValueType"] == "Secret":
            secrets[spec["name"]] = "<" + spec["name"].replace("_", "-") + ">"
        else:
            configs[spec["name"]] = "<" + spec["name"].replace("_", "-") + ">"

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
            if comments_map[key] != "":
                data['secrets'].yaml_set_comment_before_after_key(key, before=comments_map[key] + '\n')

        # Add comments for config keys
        for key in configs:
            if comments_map[key] != "":
                data['configs'].yaml_set_comment_before_after_key(key, before=comments_map[key] + '\n')

        # Dump data object back to string
        buf = io.StringIO()
        yaml.dump(data, buf)
        connection_template_with_comments = buf.getvalue()

        return connection_template_with_comments

    return connection_template


def extract_comments_mapping(keys, doc):
    comments_map = {}
    for key in keys:
        pattern = rf"(?:\:param {key}:.*|\:type {key}:.*)"
        comment = ' '.join(re.findall(pattern, doc, re.MULTILINE))
        comments_map[key] = comment

    return comments_map
