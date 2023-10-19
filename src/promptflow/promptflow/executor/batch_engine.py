from pathlib import Path
from typing import Dict, Union

from promptflow._utils.load_data import load_data
from promptflow.contracts.multimedia import Image, PFBytes
from promptflow.executor import FlowExecutor
from promptflow.executor._result import BulkResult


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
        input_dicts = self.get_input_dicts(input_dirs, inputs_mapping)
        batch_result = self.flow_executor.exec_bulk(input_dicts, run_id)
        for output in batch_result.outputs:
            output_dir = self._resolve_dir(output_dir)
            output = self.flow_executor._persist_images_from_output(output, output_dir)
        return batch_result

    def get_input_dicts(self, input_dirs: Dict[str, str], inputs_mapping: Dict[str, str]):
        """Resolve input data from input dirs and apply inputs mapping"""
        input_dicts = self._resolve_data(input_dirs)
        return self.flow_executor.validate_and_apply_inputs_mapping(input_dicts, inputs_mapping)

    def _resolve_data(self, input_dirs: Dict[str, str]):
        """Resolve input data from input dirs"""
        result = {}
        for input_key, input_dir in input_dirs.items():
            input_dir = self._resolve_dir(input_dir)
            file_data = load_data(input_dir)
            for each_line in file_data:
                self._resolve_image_path(input_dir, each_line)
            result[input_key] = file_data
        return result

    def _resolve_dir(self, dir: Union[str, Path]) -> Path:
        """Resolve input dir to absolute path"""
        path = dir if isinstance(dir, Path) else Path(dir)
        if not path.is_absolute():
            path = self.flow_executor._working_dir / path
        return path

    def _resolve_image_path(self, input_dir: Path, one_line_data: dict):
        """Resolve image path to absolute path in one line data"""
        for key, value in one_line_data.items():
            if isinstance(value, list):
                for each_item in value:
                    each_item = BatchEngine.resolve_image(input_dir, each_item)
                one_line_data[key] = value
            elif isinstance(value, dict):
                one_line_data[key] = BatchEngine.resolve_image(input_dir, value)
        return one_line_data

    @staticmethod
    def resolve_image(input_dir: Path, data_dict: dict):
        """Resolve image path to absolute path in data dict"""
        input_dir = input_dir.parent if input_dir.is_file() else input_dir
        if PFBytes._is_multimedia_dict(data_dict):
            for key in data_dict:
                _, resource = Image._get_multimedia_info(key)
                if resource == "path":
                    data_dict[key] = str(input_dir / data_dict[key])
        return data_dict
