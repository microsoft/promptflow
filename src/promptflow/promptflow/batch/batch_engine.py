import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.flow_utils import apply_default_value_for_input
from promptflow._utils.logger_utils import logger
from promptflow._utils.utils import dump_list_to_jsonl, resolve_dir_to_absolute
from promptflow.batch._batch_inputs_processor import BatchInputsProcessor
from promptflow.batch.base_executor_proxy import AbstractExecutorProxy
from promptflow.batch.python_executor_proxy import PythonExecutorProxy
from promptflow.contracts.flow import Flow
from promptflow.contracts.run_info import FlowRunInfo, Status
from promptflow.executor._result import BulkResult
from promptflow.executor.flow_executor import LINE_NUMBER_KEY
from promptflow.storage._run_storage import AbstractRunStorage

OUTPUT_FILE_NAME = "output.jsonl"


class BatchEngine:
    """This class is used to execute flows in batch mode"""

    executor_proxy_classes: Mapping[str, AbstractExecutorProxy] = {
        "python": PythonExecutorProxy,
    }

    @classmethod
    def register_executor(cls, type, executor_proxy_cls: AbstractExecutorProxy):
        cls.executor_proxy_classes[type] = executor_proxy_cls

    def __init__(
        self,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
    ):
        self._flow_file = flow_file
        self._working_dir = Flow._resolve_working_dir(flow_file, working_dir)
        self._flow = Flow.from_yaml(flow_file, working_dir=working_dir)
        executor_proxy_cls = self.executor_proxy_classes[self._flow.code_language]
        with _change_working_dir(self._working_dir):
            self._executor_proxy: AbstractExecutorProxy = executor_proxy_cls.create(
                flow_file, working_dir, connections=connections, storage=storage
            )

    def run(
        self,
        input_dirs: Dict[str, str],
        inputs_mapping: Dict[str, str],
        output_dir: Path,
        run_id: Optional[str] = None,
        max_lines_count: Optional[int] = None,
        raise_on_line_failure: Optional[bool] = False,
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
        batch_input_processor = BatchInputsProcessor(self._working_dir, self._flow.inputs, max_lines_count)
        batch_inputs = batch_input_processor.process_batch_inputs(input_dirs, inputs_mapping)
        # run flow in batch mode
        output_dir = resolve_dir_to_absolute(self._working_dir, output_dir)
        with _change_working_dir(self._working_dir):
            batch_result = self._exec_batch(batch_inputs, run_id, output_dir, raise_on_line_failure)
        # persist outputs to output dir
        self._persist_outputs(batch_result.outputs, output_dir)
        return batch_result

    def _exec_batch(
        self,
        batch_inputs: List[Dict[str, Any]],
        run_id: str = None,
        output_dir: Path = None,
        raise_on_line_failure: bool = False,
    ) -> BulkResult:
        # Apply default value in early stage, so we can use it both in line execution and aggregation nodes execution.
        batch_inputs = [
            apply_default_value_for_input(self._flow.inputs, each_line_input) for each_line_input in batch_inputs
        ]
        run_id = run_id or str(uuid.uuid4())
        line_results = self._executor_proxy.exec_batch(batch_inputs, run_id, output_dir)
        self._handle_line_failures([r.run_info for r in line_results], raise_on_line_failure)
        aggr_results = self._executor_proxy.exec_aggregation(batch_inputs, line_results, run_id)
        outputs = [
            {LINE_NUMBER_KEY: r.run_info.index, **r.output}
            for r in line_results
            if r.run_info.status == Status.Completed
        ]
        return BulkResult(
            outputs=outputs,
            metrics=aggr_results.metrics,
            line_results=line_results,
            aggr_results=aggr_results,
        )

    def _handle_line_failures(self, run_infos: List[FlowRunInfo], raise_on_line_failure: bool = False):
        """Handle line failures in batch run"""
        failed = [i for i, r in enumerate(run_infos) if r.status == Status.Failed]
        failed_msg = None
        if len(failed) > 0:
            failed_indexes = ",".join([str(i) for i in failed])
            first_fail_exception = run_infos[failed[0]].error["message"]
            if raise_on_line_failure:
                failed_msg = "Flow run failed due to the error: " + first_fail_exception
                raise Exception(failed_msg)

            failed_msg = (
                f"{len(failed)}/{len(run_infos)} flow run failed, indexes: [{failed_indexes}],"
                f" exception of index {failed[0]}: {first_fail_exception}"
            )
            logger.error(failed_msg)

    def _persist_outputs(self, outputs: List[Mapping[str, Any]], output_dir: Path):
        """Persist outputs to json line file in output directory"""
        output_file = output_dir / OUTPUT_FILE_NAME
        dump_list_to_jsonl(output_file, outputs)
