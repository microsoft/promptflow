from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.utils import dump_list_to_jsonl, resolve_dir_to_absolute
from promptflow.batch_engine._batch_inputs_processor import BatchInputsProcessor
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
        run_id: Optional[str] = None,
        max_lines_count: Optional[int] = None,
    ) -> BulkResult:
        """Run flow in batch mode

        :param input_dirs: The directories path of input files
        :type input_dirs: Dict[str, str]
        :param inputs_mapping: The mapping of input names to their corresponding values.
        :type inputs_mapping: Dict[str, str]
        :param output_dir: output dir
        :type output_dir: The directory path of output files
        :param run_id: The run id of this run
        :type run_id: Optional[str]
        :param max_lines_count: The max count of inputs. If it is None, all inputs will be used.
        :type max_lines_count: Optional[int]
        :return: The result of this batch run
        :rtype: ~promptflow.executor._result.BulkResult
        """
        # resolve input data from input dirs and apply inputs mapping
        batch_input_processor = BatchInputsProcessor(
            self.flow_executor._working_dir, self.flow_executor._flow.inputs, max_lines_count
        )
        batch_inputs = batch_input_processor.process_batch_inputs(input_dirs, inputs_mapping)
        # run flow in batch mode
        output_dir = resolve_dir_to_absolute(self.flow_executor._working_dir, output_dir)
        with _change_working_dir(self.flow_executor._working_dir):
            batch_result = self.flow_executor.exec_bulk(batch_inputs, run_id, output_dir=output_dir)
        # persist outputs to output dir
        self._persist_outputs(batch_result.outputs, output_dir)
        return batch_result

    def _persist_outputs(self, outputs: List[Mapping[str, Any]], output_dir: Path):
        """Persist outputs to json line file in output directory"""
        output_file = output_dir / OUTPUT_FILE_NAME
        dump_list_to_jsonl(output_file, outputs)
