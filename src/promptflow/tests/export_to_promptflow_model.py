import argparse
import copy
import json
import os
from pathlib import Path

tool_suffix_mapping = {"python": ".py", "llm": ".jinja2", "prompt": ".jinja2"}

connection_types = [
    "BingConnection",
    "OpenAIConnection",
    "AzureOpenAIConnection",
    "CustomConnection",
    "AzureContentSafetyConnection",
    "SerpConnection",
    "CognitiveSearchConnection",
    "SubstrateLLMConnection",
]


def dump_json(data, target_file):
    with open(target_file, "w") as fout:
        json.dump(data, fout, indent=2)


def add_node_connection(connections_json, node_name, connection_value):
    if "nodes" not in connections_json:
        connections_json["nodes"] = []
    select_node = [node for node in connections_json["nodes"] if node["name"] == node_name]
    if len(select_node) == 0:
        the_node = {"name": node_name, "connection": copy.deepcopy(connection_value)}
        connections_json["nodes"].append(the_node)
    else:
        the_node = select_node[0]


def add_tool_input(connections_json, tool_name, input_name, input_value):
    if "tools" not in connections_json:
        connections_json["tools"] = []

    select_tool = [tool for tool in connections_json["tools"] if tool["name"] == tool_name]
    if len(select_tool) == 0:
        the_tool = {"name": tool_name, "inputs": {}}
        connections_json["tools"].append(the_tool)
    else:
        the_tool = select_tool[0]

    if input_name not in the_tool["inputs"]:
        the_tool["inputs"][input_name] = copy.deepcopy(input_value)


def add_node_input(connections_json, node_name, input_name, input_value):
    if "nodes" not in connections_json:
        connections_json["nodes"] = []
    select_node = [node for node in connections_json["nodes"] if node["name"] == node_name]
    if len(select_node) == 0:
        the_node = {"name": node_name, "inputs": {}}
        connections_json["nodes"].append(the_node)
    else:
        the_node = select_node[0]

    if "inputs" not in the_node:
        the_node["inputs"] = {}

    if input_name not in the_node["inputs"]:
        the_node["inputs"][input_name] = copy.deepcopy(input_value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_target_dir", type=str, required=True)
    parser.add_argument("--values_target_dir", type=str, required=True)
    parser.add_argument("--payload", type=str, required=True)
    parser.add_argument("--flow_name", type=str, required=True)
    parser.add_argument("--type", type=str, default="sample")
    parser.add_argument("--stage", type=str, default="test")
    parser.add_argument("--description", type=str, default="This is my flow")
    args = parser.parse_args()

    with open(args.payload) as fin:
        data = json.load(fin)

    model_target_dir = Path(args.model_target_dir)
    model_target_dir.mkdir(parents=True, exist_ok=True)
    values_target_dir = Path(args.values_target_dir)
    values_target_dir.mkdir(parents=True, exist_ok=True)
    flowGraph = data["flow"]["flowGraph"]
    flows = {
        "id": args.flow_name,
        "name": args.flow_name,
        "nodes": flowGraph["nodes"],
        "inputs": flowGraph["inputs"],
        "outputs": flowGraph["outputs"],
        "tools": flowGraph["tools"],
    }

    tool_node_name_mappings = {}
    for node in flows["nodes"]:
        if node["tool"] in tool_node_name_mappings.keys():
            raise Exception("Two or more nodes use the same tool.")
        tool_node_name_mappings[node["tool"]] = node["name"]
        node["tool"] = node["name"]

    node_variants = data["flow"]["nodeVariants"]
    node_variants_settings_map = {}
    for node, settings in node_variants.items():
        if len(settings["variants"]) > 1:
            for variant, variant_setting in settings["variants"].items():
                if variant_setting["node"]["tool"] in tool_node_name_mappings.keys():
                    variant_setting["node"]["tool"] = tool_node_name_mappings[variant_setting["node"]["tool"]]
            settings_file_name = f"{node}_variants_settings.json"
            dump_json(settings, model_target_dir / settings_file_name)
            node_variants_settings_map[node] = settings_file_name

    codes = {}
    for tool in data["flow"]["flowGraph"]["tools"]:
        if tool["name"] in tool_node_name_mappings.keys():
            tool["name"] = tool_node_name_mappings[tool["name"]]

        if "code" in tool:
            suffix = tool_suffix_mapping[tool["type"]]
            source_file = tool["name"] + suffix
            tool["source"] = tool.get("source", source_file)
            with open(model_target_dir / source_file, "w") as fout:
                fout.write(tool.pop("code"))
            codes[tool["name"]] = {"type": tool["type"], "source": source_file}

    meta_dict = {
        "type": args.type,
        "stage": args.stage,
        "name": args.flow_name,
        "description": args.description,
        "flow": "flow.json",
        "batch_inputs": "samples.json",
        "codes": codes,
        "details": {"type": ["markdown"], "source": "README.md"},
        "node_variants": node_variants_settings_map,
    }

    values_json = {}
    connections_names = {}
    # Clean up for tools
    for tool in flows["tools"]:
        if "lkgCode" in tool:
            tool.pop("lkgCode")
        if "inputs" in tool:
            for input_name, input_value in tool["inputs"].items():
                if input_value["type"][0] in connection_types:
                    if tool["name"] not in connections_names.keys():
                        connections_names[tool["name"]] = []
                    connections_names[tool["name"]].append(input_value["name"])

                if "value" in input_value.keys():
                    input_value.pop("value")

    # Clean up for nodes
    for node in flows["nodes"]:
        if "connection" in node:
            add_node_connection(values_json, node["name"], node["connection"])
            node["connection"] = ""
        for input_name, input_value in node["inputs"].items():
            if node["tool"] in connections_names.keys() and input_name in connections_names[node["tool"]]:
                add_node_input(values_json, node["name"], input_name, input_value)
                node["inputs"][input_name] = ""
            elif input_name == "deployment_name":
                add_node_input(values_json, node["name"], input_name, input_value)
                node["inputs"][input_name] = ""

    if len(values_json) != 0:
        dump_json(values_json, values_target_dir / "values.json")

    dump_json(meta_dict, model_target_dir / "meta.json")
    dump_json(flows, model_target_dir / "flow.json")
    dump_json(data["flowSubmitRunSettings"]["batch_inputs"], model_target_dir / "samples.json")
    with open(os.path.join(args.model_target_dir, "README.md"), "w") as w:
        w.write("### " + args.flow_name)

    print("Export completed")
