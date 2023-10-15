from typing import Dict

from promptflow._utils.load_data import load_data
from promptflow.executor.flow_executor import FlowExecutor


class BatchEngine:
    def __init__(self, flow_executor: FlowExecutor):
        self.flow_executor = flow_executor

    def run(
        self,
        input_dirs: Dict[str, str],
        inputs_mapping: Dict[str, str],
        output_dir: str,
        run_id: str = None,
    ):
        # 1. load data
        input_dicts = self._resolve_data(input_dirs)
        # 2. apply inputs mapping
        mapped_inputs = self._apply_inputs_mapping(input_dirs, input_dicts, inputs_mapping)
        # 3. execute batch run
        batch_result = self.flow_executor.exec_bulk(mapped_inputs, run_id)
        return batch_result

    def _resolve_data(self, input_dirs: Dict[str, str]):
        result = {}
        for input_key, local_file in input_dirs.items():
            result[input_key] = load_data(local_file)
        return result

    def _apply_inputs_mapping(
        self,
        input_dirs: Dict[str, str],
        input_dicts: Dict[str, list],
        inputs_mapping: Dict[str, str],
    ):
        inputs = self.flow_executor.validate_and_apply_inputs_mapping(input_dicts, inputs_mapping)
        return inputs
