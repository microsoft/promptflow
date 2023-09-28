import re
import sys
from pathlib import Path

import yaml

from promptflow._utils.utils import camel_to_snake


class Node:
    def __init__(self, *, name, indent, source_func, inline_comment, inputs):
        self._name = name
        self._indent = indent
        self._inputs = inputs
        self._source_func = source_func
        self._inline_comment = inline_comment

    @classmethod
    def from_yaml(cls, yaml: str, start: int, end: int):
        return

    @classmethod
    def _parse_input(cls, input_str):
        if "." not in input_str:
            return f"${{{camel_to_snake(input_str)}.output}}"
        else:
            assert input_str.startswith("inputs.")
            return f"${{inputs.{camel_to_snake(input_str.split('.', 1)[1])}}}"

    @classmethod
    def from_cs(cls, cs: str):
        if len(cs.strip()) == 0:
            return None
        if cs.strip().startswith("//"):
            return None

        assert cs.count("=") == 1, f"Invalid line: {cs}"
        clarification, call = cs.split("=")
        indent = len(clarification) - len(clarification.lstrip())
        pieces = re.split(r"\s+", clarification.strip())
        if len(pieces) == 2:
            # var nodeName = ToolFunc(inputs.InputName); // inline comment
            output_cls, name = pieces

            assert call.count(";") == 1, f"Invalid line: {cs}"
            clear_call, inline_comment = call.split(";")
            clear_call = re.sub(r"\s+", "", clear_call)

            m = re.match(r"([a-zA-Z0-9.]+)\((.+)\)$", clear_call)
            assert m, f"Invalid line: {cs}, error in parsing {clear_call}"

            re.match(r"^(\s*)public\s+class\s+(\w+)\s*{\s*$", cs)
            source_func = m.group(1)
            inputs = [cls._parse_input(_in) for _in in m.group(2).split(",")]

            return cls(
                indent=indent,
                name=name,
                inline_comment=inline_comment,
                source_func=source_func,
                inputs=inputs,
            )
        elif len(pieces) == 1 and pieces[0].startswith("output."):
            # output.OutputName = ToolFunc(inputs.InputName); // inline comment
            return camel_to_snake(pieces[0].split(".", 1)[1]), cls._parse_input(call.strip().strip(";"))
        else:
            raise AssertionError(f"Invalid line: {cs}")


class Graph:
    def __init__(self, cs_path: str):
        self._nodes = []
        self._prefix, self._execution_code, self._suffix = self.split_code(
            Path(cs_path).read_text(encoding="utf-8").splitlines()
        )
        self._execution_nodes, self._outputs = [], {}
        for line in self._execution_code:
            item = Node.from_cs(line)
            if item is None:
                continue
            if isinstance(item, tuple):
                self._outputs[item[0]] = item[1]
            elif isinstance(item, Node):
                self._execution_nodes.append(item)
            else:
                raise AssertionError(f"Invalid item: {item}")
        self._inputs = self.gather_inputs_from_nodes()

    def gather_inputs_from_nodes(self):
        inputs = []
        for node in self._execution_nodes:
            if node is None:
                continue
            for reference in node._inputs:
                m = re.match(r"^\${inputs\.(.+)}$", reference)
                if m:
                    inputs.append(m.group(1))
        return inputs

    @classmethod
    def split_code(cls, lines: list[str]):
        prefix, suffix = [], []

        execution_code = []
        execution_status = 0
        for line in lines:
            if execution_status == 0:
                prefix.append(line)
            elif execution_status == 1:
                execution_code.append(line)
            elif execution_status == 2:
                suffix.append(line)

            if line.strip() == "// execution code: start":
                execution_status = 1
            elif line.strip() == "// execution code: end":
                suffix.append(execution_code.pop())
                execution_status = 2

        return prefix, execution_code, suffix

    @classmethod
    def from_yaml(cls, yaml: str):
        return cls()

    def dump_yaml(self, yaml_path: str):
        obj = {
            "inputs": {input_: {"type": "string"} for input_ in self._inputs},
            "outputs": {k: {"type": "string", "reference": v} for k, v in self._outputs.items()},
            "nodes": [],
        }
        for node in self._execution_nodes:
            inputs_obj = {}
            for item in node._inputs:
                # seems that this can't be resolved from text
                inputs_obj["prompt"] = item
            obj["nodes"].append(
                {
                    "name": node._name,
                    "type": "csharp",
                    "source": {
                        "type": "func",
                        "path": node._source_func,
                    },
                    "inputs": inputs_obj,
                }
            )
        yaml.dump(obj, Path(yaml_path).open("w"), indent=2, sort_keys=False)
        return


class Transformer:
    def __init__(self, flow_cs: str):
        self._flow_cs = Path(flow_cs).absolute()
        flow_dir = self._flow_cs.parent.as_posix()
        self._flow_dag_yaml = Path(f"{flow_dir}/flow.dag.yaml").absolute()
        self._last_flow_dag_yaml = Path(f"{flow_dir}/.promptflow/transfer-backup/flow.dag.yaml").absolute()
        self._last_flow_cs = Path(f"{flow_dir}/.promptflow/transfer-backup/Flow.cs").absolute()
        self._last_flow_cs.parent.mkdir(parents=True, exist_ok=True)

    def _backup(self):
        if self._flow_dag_yaml.is_file():
            self._last_flow_dag_yaml.write_bytes(self._flow_dag_yaml.read_bytes())
        if self._flow_cs.is_file():
            self._last_flow_cs.write_bytes(self._flow_cs.read_bytes())
        return

    def generate_flow_dag_yaml(self):
        Graph(self._flow_cs.as_posix()).dump_yaml(self._flow_dag_yaml.as_posix())

    def generate_flow_cs(self):
        return

    def _sync(self):
        if not self._flow_dag_yaml.is_file() and not self._flow_cs.is_file():
            print("No flow.dag.yaml or Flow.cs found.")
            return

        if not self._flow_dag_yaml.exists():
            self.generate_flow_dag_yaml()
            return
        if not self._flow_cs.exists():
            self.generate_flow_cs()
            return

        flow_dag_yaml_updated = self._flow_dag_yaml.read_bytes() != self._last_flow_dag_yaml.read_bytes()
        flow_cs_updated = self._flow_cs.read_bytes() != self._last_flow_cs.read_bytes()

        if flow_cs_updated and flow_dag_yaml_updated:
            print("Support 1-side change sync only for now but both flow.dag.yaml and Flow.cs are updated.")
            return

        if not flow_cs_updated and not flow_dag_yaml_updated:
            print("No change detected.")
            return

        if flow_cs_updated:
            # TODO: update flow.dag.yaml
            self.generate_flow_dag_yaml()

    def sync(self):
        self._sync()
        self._backup()
        return


if __name__ == "__main__":
    Transformer(sys.argv[1]).sync()
