# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import re
import textwrap
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
      {{ configs_comments }}{% for key, value in configs.items() %}  
      {{ key }}: "{{ value -}}"{% endfor %}  
    secrets:  # must-have
      {{ secrets_comments }}{% for key, value in secrets.items() %}  
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
  
    # Extract docstring comments
    secrets_comments, configs_comments = "", ""
    if cls.__doc__ is not None:
        secrets_comments = extract_comments(secrets.keys(), cls.__doc__)
        configs_comments = extract_comments(configs.keys(), cls.__doc__)

    # Prepare data for template  
    data = {  
        "custom_type": cls.__name__,  
        "module": cls.__module__,  
        "package": package,  
        "package_version": package_version,  
        "configs": configs,  
        "secrets": secrets,  
        "secrets_comments": secrets_comments,  
        "configs_comments": configs_comments,  
    }  
  
    return connection_template.render(data)  


def extract_comments(keys, doc):  
    pattern = "|".join(rf"(?:\:param {key}.*|\:type {key}.*)" for key in keys)  
    comments = '\n'.join(re.findall(pattern, doc, re.MULTILINE))
    indented_comments = textwrap.indent(comments, ' ' * 6)  
    return '"""\n' + indented_comments + '\n      """'
