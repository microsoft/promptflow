# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from jinja2 import Template


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

    configs = {}
    secrets = {}
    connection_template = Template(connection_template_str)
    for spec in connection_spec["configSpecs"]:
        if spec["configValueType"] == "Secret":
            secrets[spec["name"]] = "<" + spec["name"].replace("_", "-") + ">"
        else:
            configs[spec["name"]] = "<" + spec["name"].replace("_", "-") + ">"

    data = {
        "custom_type": cls.__name__,
        "module": cls.__module__,
        "package": package,
        "package_version": package_version,
        "configs": configs,
        "secrets": secrets,
    }

    return connection_template.render(data)
