from pathlib import Path
from typing import Any, Dict, List, Mapping, Union

from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.load_data import load_data
from promptflow._utils.multimedia_utils import resolve_multimedia_data_recursively
from promptflow._utils.utils import dump_list_to_jsonl
from promptflow.executor._result import BulkResult
from promptflow.executor.flow_executor import FlowExecutor

OUTPUT_FILE_NAME = "output.jsonl"


class BatchEngine:
    """This class is used to execute flows in batch mode

    :param flow_executor: The executor will be used to run flow in batch mode
    :type flow_executor: ~promptflow.executor.FlowExecutor
    """

    def __init__(self, flow_executor: FlowExecutor):
        """Initialize a BatchEngine object.

        :param flow_executor: The executor will be used to run flow in batch mode
        :type flow_executor: ~promptflow.executor.FlowExecutor
        """
        self.flow_executor = flow_executor

    def run(
        self,
        input_dirs: Dict[str, str],
        inputs_mapping: Dict[str, str],
        output_dir: Path,
        run_id: str = None,
        max_inputs_count: int = None,
    ) -> BulkResult:
        """Run flow in batch mode

        :param input_dirs: The directories path of input files
        :type input_dirs: Dict[str, str]
        :param inputs_mapping: The mapping of input names to their corresponding values.
        :type inputs_mapping: Dict[str, str]
        :param output_dir: output dir
        :type output_dir: The directory path of output files
        :param run_id: The run id of this run
        :type run_id: str
        :param max_inputs_count: The max count of inputs
        :type max_inputs_count: int
        :return: The result of this batch run
        :rtype: ~promptflow.executor._result.BulkResult
        """
        # resolve input data from input dirs and apply inputs mapping
        input_dicts = self._resolve_data(input_dirs, max_inputs_count)
        mapped_inputs = self.flow_executor.validate_and_apply_inputs_mapping(input_dicts, inputs_mapping)
        # run flow in batch mode
        output_dir = self._resolve_dir(output_dir)
        with _change_working_dir(self.flow_executor._working_dir):
            batch_result = self.flow_executor.exec_bulk(mapped_inputs, run_id, output_dir=output_dir)
        # persist outputs to output dir
        self._persist_outputs(batch_result.outputs, output_dir)
        return batch_result

    def _resolve_data(self, input_dirs: Dict[str, str], max_inputs_count: int = None):
        """Resolve input data from input dirs"""
        result = {}
        for input_key, input_dir in input_dirs.items():
            input_dir = self._resolve_dir(input_dir)
            result[input_key] = self._resolve_data_from_input_path(input_dir, max_inputs_count)
        return result

    def _resolve_data_from_input_path(self, input_path: Path, max_inputs_count: int = None):
        """Resolve input data from directory"""
        result = []
        if input_path.is_file():
            result.extend(resolve_multimedia_data_recursively(input_path.parent, load_data(input_path)))
        else:
            for input_file in input_path.rglob("*"):
                if input_file.is_file():
                    result.extend(resolve_multimedia_data_recursively(input_file.parent, load_data(input_file)))
                    if max_inputs_count and len(result) >= max_inputs_count:
                        break
        return result[:max_inputs_count] if max_inputs_count and len(result) > max_inputs_count else result

    def _resolve_dir(self, dir: Union[str, Path]) -> Path:
        """Resolve input dir to absolute path"""
        path = dir if isinstance(dir, Path) else Path(dir)
        if not path.is_absolute():
            path = self.flow_executor._working_dir / path
        return path

    def _persist_outputs(self, outputs: List[Mapping[str, Any]], output_dir: Path):
        """Persist outputs to json line file in output directory"""
        output_file = output_dir / OUTPUT_FILE_NAME
        dump_list_to_jsonl(output_file, outputs)
