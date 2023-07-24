import os
import yaml
import json

from promptflow.utils.generate_tool_meta_utils import generate_prompt_meta, generate_python_meta


def generate_code_tool_meta_from_node(node, flow_dir, code_tools):
    if 'source' not in node:
        return

    node_source_type = node['source']['type']
    if node_source_type == 'code':
        node_source_path = node['source']['path']
        node_source_file = os.path.join(flow_dir, node_source_path)
        with open(node_source_file, 'r') as file:
            node_source = file.read()

        node_type = node['type'].lower()
        if node_type == 'llm':
            result = generate_prompt_meta(node['name'], node_source)
        elif node_type == 'prompt':
            result = generate_prompt_meta(node['name'], node_source, prompt_only=True)
        else:
            result = generate_python_meta(node['name'], node_source)

        meta = json.loads(result)
        del meta['name']
        del meta['code']
        code_tools[node_source_path] = meta


def generate_code_tool_meta(yaml_file):
    # Get the input file's directory path
    flow_dir = os.path.dirname(yaml_file)

    # Load the YAML file
    with open(yaml_file, 'r') as file:
        flow = yaml.safe_load(file)

    nodes = flow["nodes"]
    code_tools = {}
    for node in nodes:
        generate_code_tool_meta_from_node(node, flow_dir, code_tools)

    node_variants = flow["node_variants"]
    for node_name in list(node_variants.keys()):
        variants = node_variants[node_name]['variants']
        for variant_id in variants.keys():
            node = variants[variant_id]['node']
            node['name'] = node_name
            generate_code_tool_meta_from_node(node, flow_dir, code_tools)

    for node in nodes:
        generate_code_tool_meta_from_node(node, flow_dir, code_tools)

    # Create the output directory path
    output_dir = os.path.join(flow_dir, ".promptflow")

    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Get the output file path
    output_file = os.path.join(output_dir, "flow.tools.json")

    if os.path.exists(output_file):
        # Update the "code" field in the existing JSON file
        with open(output_file, 'r') as file:
            existing_data = json.load(file)

        tools_json = existing_data
        tools_json["code"] = code_tools
    else:
        tools_json = {
            "package": {},
            "code": code_tools
        }

    # Create a new JSON file and output the content
    with open(output_file, 'w') as file:
        json.dump(tools_json, file, indent=4)

    print(f"Output file created/updated: {output_file}")


# Usage example
input_yaml_file = "./outputs/web_classification/flow.dag.yaml"
generate_code_tool_meta(input_yaml_file)
