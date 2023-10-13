from typing import Dict

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
        self._load_data()
        # 2. apply inputs mapping
        self._apply_inputs_mapping()
        # 3. execute batch run
        batch_result = self.flow_executor.exec_bulk()
        return batch_result

    def _load_data(self, input_dirs: Dict[str, str]):
        pass

    def _apply_inputs_mapping(self, inputs_mapping: Dict[str, str]):
        pass
