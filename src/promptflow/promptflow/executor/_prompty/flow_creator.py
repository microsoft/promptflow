from pathlib import Path
import yaml
import shutil
import os


default_yaml = """inputs: {}
outputs:
  output:
    type: string
    reference: ${completion.output}
nodes:
- name: completion
  type: python
  source:
    type: code
    path: .promptflow/completion.py
  inputs:
    prompt_tpl_file: sample.prompt
    deployment_name: gpt-35-turbo
"""


def parse_config(prompt_file):
    with open(prompt_file, "r") as f:
        prompt_tpl = f.read()
    left = prompt_tpl.find("---") + 3
    right = prompt_tpl.rfind("---")
    config_yaml = prompt_tpl[left:right]
    return yaml.safe_load(config_yaml)


def create_flow_for_prompt(prompt_file):
    file_name = Path(prompt_file).name
    prompt_config = parse_config(prompt_file)
    default_flow = yaml.safe_load(default_yaml)
    inputs_config = prompt_config.get("inputs", {})
    default_flow["inputs"] = {
        k: {"type": "string", "default": v}
        for k, v in inputs_config.items()
    }
    dummy_node_inputs = default_flow["nodes"][0]["inputs"]
    dummy_node_inputs.update({
        "prompt_tpl_file": file_name,
        **{k: f"${{inputs.{k}}}" for k in inputs_config},
    })
    model_config = prompt_config.get("model", {})
    if "deployment" in model_config:
        dummy_node_inputs["deployment_name"] = model_config["deployment"]

    target_folder = Path(prompt_file).parent / ".promptflow"
    target_folder.mkdir(exist_ok=True)
    yaml_file = Path(target_folder) / "flow.dag.yaml"
    with open(yaml_file, "w") as f:
        yaml.safe_dump(default_flow, f)
    completion_file = Path(__file__).parent / "completion.py"
    shutil.copy(str(completion_file), os.path.join(target_folder, "completion.py"))
    return yaml_file
