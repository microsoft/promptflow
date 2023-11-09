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
        :return: The result of this batch run
        :rtype: ~promptflow.executor._result.BulkResult
        """
        # resolve input data from input dirs and apply inputs mapping
        input_dicts = self._resolve_data(input_dirs)
        mapped_inputs = self.flow_executor.validate_and_apply_inputs_mapping(input_dicts, inputs_mapping)
        # run flow in batch mode
        output_dir = self._resolve_dir(output_dir)
        with _change_working_dir(self.flow_executor._working_dir):
            batch_result = self.flow_executor.exec_bulk(mapped_inputs, run_id, output_dir=output_dir)
        # persist outputs to output dir
        self._persist_outputs(batch_result.outputs, output_dir)
        return batch_result

    def _resolve_data(self, input_dirs: Dict[str, str]):
        """Resolve input data from input dirs"""
        result = {}
        for input_key, input_dir in input_dirs.items():
            input_dir = self._resolve_dir(input_dir)
            file_data = load_data(input_dir)
            resolve_multimedia_data_recursively(input_dir, file_data)
            result[input_key] = file_data
        return result

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


from ._result import LineResult


class AbstractExecutor:

    @classmethod
    def create(
        cls,
        yaml_file,
        working_dir,
    ) -> "AbstractExecutor":
        """Create a new executor"""
        raise NotImplementedError()

    def destroy(self):
        pass

    def exec_line(self, inputs, index, run_id) -> LineResult:
        raise NotImplementedError()


class APIBasedExecutor(AbstractExecutor):
    @property
    def api_endpoint(self) -> str:
        raise NotImplementedError()

    def exec_line(self, inputs, index, run_id) -> LineResult:
        import requests
        timeout = 600
        payload = {"run_id": run_id, "line_number": index, "inputs": inputs}
        resp = requests.post(self.api_endpoint, json=payload, timeout=timeout)
        return LineResult.from_dict(resp.json())


class PythonExecutor(AbstractExecutor):

    @classmethod
    def create(
        cls,
        yaml_file,
        working_dir,
    ) -> "AbstractExecutor":
        """Create a new executor"""
        return cls(yaml_file, working_dir)

    def __init__(self, yaml_file, working_dir):
        self._yaml_file = yaml_file
        self._working_dir = working_dir
        self._executor = FlowExecutor.create(
            self._yaml_file,
            connections={},
            working_dir=self._working_dir,
        )

    def destroy(self):
        pass

    def exec_line(self, inputs, index, run_id) -> LineResult:
        return self._executor.exec_line(inputs, index, run_id=run_id)


from promptflow.storage import AbstractRunStorage


class NewBatchEngine:
    executor_classes = {
    }

    @classmethod
    def register_executor(cls, type, executor_cls: AbstractExecutor):
        cls.executor_classes[type] = executor_cls

    def __init__(self, yaml_file, storage: AbstractRunStorage, working_dir = None):
        if not working_dir:
            working_dir = Path(yaml_file).parent
        working_dir = Path(working_dir).resolve()
        executor_type = "python"
        self._executor_cls = self.executor_classes[executor_type]
        with _change_working_dir(working_dir):
            self._executor: AbstractExecutor = self._executor_cls.create(yaml_file, working_dir)
        self._storage = storage
        self._working_dir = working_dir
        self._yaml_file = yaml_file

    def _resolve_data(self, input_dirs: Dict[str, str]):
        """Resolve input data from input dirs"""
        result = {}
        for input_key, input_dir in input_dirs.items():
            input_dir = self._resolve_dir(input_dir)
            file_data = load_data(input_dir)
            resolve_multimedia_data_recursively(input_dir, file_data)
            result[input_key] = file_data
        return result

    def _resolve_dir(self, dir: Union[str, Path]) -> Path:
        """Resolve input dir to absolute path"""
        path = dir if isinstance(dir, Path) else Path(dir)
        if not path.is_absolute():
            path = self._working_dir / path
        return path

    def _persist_outputs(self, outputs: List[Mapping[str, Any]], output_dir: Path):
        """Persist outputs to json line file in output directory"""
        output_file = output_dir / OUTPUT_FILE_NAME
        dump_list_to_jsonl(output_file, outputs)

    def run(
        self,
        input_dirs: Dict[str, str],
        inputs_mapping: Dict[str, str],
        output_dir: Path,
        run_id: str = None,
    ) -> BulkResult:
        with _change_working_dir(self._working_dir):
            input_dicts = self._resolve_data(input_dirs)
            mapped_inputs = FlowExecutor._apply_inputs_mapping_for_all_lines(input_dicts, inputs_mapping)
            # run flow in batch mode
            output_dir = self._resolve_dir(output_dir)
            line_results = []
            outputs = []
            for i, each_line_input in enumerate(mapped_inputs):
                line_result = self._executor.exec_line(each_line_input, i, run_id=run_id)
                for node_run in line_result.node_run_infos.values():
                    self._storage.persist_node_run(node_run)
                self._storage.persist_flow_run(line_result.run_info)
                line_results.append(line_result)
                from promptflow.contracts.run_info import Status
                if line_result.run_info.status == Status.Completed:
                    outputs.append(line_result.output)
            batch_result = BulkResult(
                outputs=outputs,
                metrics={},
                line_results=line_results,
                aggr_results=None,
            )

            # persist outputs to output dir
            self._persist_outputs(batch_result.outputs, output_dir)
            return batch_result
