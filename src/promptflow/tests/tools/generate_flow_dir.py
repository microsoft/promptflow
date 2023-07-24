import os
import json
import yaml


def get_code_extension(type):
    type_exts = {
        "python": ".py",
        "llm": ".jinja2",
        "prompt": ".jinja2"
    }
    return type_exts[type]


def reorder_keys(json_obj, key_order):
    # Create a new dictionary with the keys in the desired order
    new_json_obj = {key: json_obj[key] for key in key_order if key in json_obj}

    # Add the remaining keys to the new dictionary in their original order
    for key in json_obj:
        if key not in key_order:
            new_json_obj[key] = json_obj[key]
    return new_json_obj


def update_node(node, tools, output_dir, use_variants=False):
    if use_variants:
        return {'name': node['name'], 'use_variants': True}

    # Find the tool reference
    for t in tools:
        if t['name'] == node['tool']:
            tool = t
    del node['tool']

    node['type'] = tool['type']

    if tool['is_builtin']:
        node['source'] = {
            'type': 'package',
            'tool': f"{tool['module']}.{tool['function']}"
        }
    else:
        code_path_file = f"{node['name']}{get_code_extension(node['type'])}"
        node['source'] = {
            'type': 'code',
            'path': code_path_file
        }

        code_path = os.path.join(output_dir, code_path_file)
        with open(code_path, 'w') as f:
            f.write(tool['code'])

    if 'reduce' in node:
        node['aggregation'] = node.pop('reduce')

    # Temporarily add a source reference in tool for final tools.json generation
    # Currently, tools are not shared by nodes, so they are just 1:1 mapping.
    tool['source'] = node['source']

    cleanup_false_fields(node)

    return reorder_keys(node, key_order=['name', 'type', 'source', 'inputs'])


def update_nodes(nodes, tools, output_dir, node_variants):
    return [update_node(node, tools, output_dir, use_variants=node['name'] in node_variants) for node in nodes]


def update_node_variants(node_variants, tools, output_dir):
    for node_name in list(node_variants.keys()):
        node_variant = node_variants[node_name]
        if len(node_variant['variants']) == 1:
            del node_variants[node_name]
        else:
            node_variant['default_variant_id'] = node_variant.pop('defaultVariantId')
            variants = node_variant['variants']
            for variant_id in variants.keys():
                node = variants[variant_id]['node']

                # Here reformat the node name temporarily for generating right tool name and code file name
                node['name'] = f"{node['name']}__{variant_id}" if variant_id != "variant_0" else node['name']

                node = update_node(node, tools, output_dir)
                del node['name']
                variants[variant_id]['node'] = node
            node_variants[node_name] = reorder_keys(node_variant, key_order=['default_variant_id', 'variants'])
    return node_variants


def dump_tools_json(tools, output_prompt_flow_dir):
    new_tools = {
        'package': {},
        'code': {}
    }

    for tool in tools:
        source = tool['source']
        del tool['source']

        type = source['type']
        if type == 'package':
            tool_id = source['tool']
            new_tools[type][tool_id] = tool
        elif type == 'code':
            del tool['name']
            del tool['code']
            del tool['lkgCode']
            path = source['path']
            new_tools[type][path] = tool

        del tool['is_builtin']

        # Just clean up redundant fields
        if 'inputs' in tool:
            inputs = tool['inputs']
            for input in inputs.values():
                if 'name' in input:
                    del input['name']
                if 'value' in input:
                    del input['value']

    tools_json_file = os.path.join(output_prompt_flow_dir, 'flow.tools.json')
    with open(tools_json_file, 'w') as f:
        json.dump(new_tools, f, indent=4)


def cleanup_false_fields(json_obj):
    for k in list(json_obj.keys()):
        if not json_obj[k]:
            del json_obj[k]


def convert_json_to_yaml(input_json_file, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_prompt_flow_dir = os.path.join(output_dir, '.promptflow')
    if not os.path.exists(output_prompt_flow_dir):
        os.makedirs(output_prompt_flow_dir)

    # Read JSON file
    with open(input_json_file, 'r') as f:
        flow_submission_request = json.load(f)

    flow = flow_submission_request['flow']['flowGraph']

    for input in flow['inputs'].keys():
        cleanup_false_fields(flow['inputs'][input])

    for output in flow['outputs'].keys():
        cleanup_false_fields(flow['outputs'][output])

    tools = flow['tools']
    del flow['tools']

    node_variants = flow_submission_request['flow']['nodeVariants']
    flow['node_variants'] = update_node_variants(node_variants, tools, output_dir)

    # Not dumping node_variants if it's empty
    if not flow['node_variants']:
        del flow['node_variants']

    nodes = flow['nodes']
    flow['nodes'] = update_nodes(nodes, tools, output_dir, node_variants)

    output_yaml_file = os.path.join(output_dir, 'flow.dag.yaml')
    with open(output_yaml_file, 'w') as f:
        yaml.dump(reorder_keys(flow, key_order=['inputs', 'outputs', 'nodes', 'node_variants']), f, sort_keys=False)

    dump_tools_json(tools, output_prompt_flow_dir)


# Example usage
convert_json_to_yaml('inputs/web_classification.json', 'outputs/web_classification')
convert_json_to_yaml('inputs/my_echo_prompt.json', 'outputs/my_echo_prompt')
convert_json_to_yaml('inputs/content_safety_check.json', 'outputs/content_safety_check')
convert_json_to_yaml('inputs/classification_accuracy_evaluation.json', 'outputs/classification_accuracy_evaluation')
convert_json_to_yaml('inputs/langchain_math.json', 'outputs/langchain_math')
convert_json_to_yaml('inputs/copilot.json', 'outputs/copilot')
