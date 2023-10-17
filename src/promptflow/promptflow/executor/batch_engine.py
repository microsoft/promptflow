import re
from pathlib import Path

# from promptflow.contracts.multimedia import PFBytes, Image
from typing import Dict

from promptflow._utils.load_data import load_data
from promptflow.executor.flow_executor import FlowExecutor

IMAGE_PATH_PATTERN = r"^data:image/(.*);path$"


class BatchEngine:
    def __init__(self, flow_executor: FlowExecutor):
        self.flow_executor = flow_executor

    def run(
        self,
        input_dirs: Dict[str, str],
        inputs_mapping: Dict[str, str],
        output_dir: Path,
        run_id: str = None,
    ):
        input_dicts = self.get_input_dicts(input_dirs, inputs_mapping)
        batch_result = self.flow_executor.exec_bulk(input_dicts, run_id)
        for output in batch_result.outputs:
            output = self.flow_executor._persist_images_from_output(output, output_dir)
        return batch_result

    def get_input_dicts(self, input_dirs: Dict[str, str], inputs_mapping: Dict[str, str]):
        input_dicts = self._resolve_data(input_dirs)
        return self.flow_executor.validate_and_apply_inputs_mapping(input_dicts, inputs_mapping)

    def _resolve_data(self, input_dirs: Dict[str, str]):
        result = {}
        for input_key, input_dir in input_dirs.items():
            input_dir = self._resolve_input_dir(input_dir)
            file_data = load_data(input_dir)
            for each_line in file_data:
                self._resolve_image_path(input_dir, each_line)
            result[input_key] = file_data
        return result

    def _resolve_input_dir(self, input_dir: str):
        input_path = Path(input_dir)
        if not input_path.is_absolute():
            input_path = self.flow_executor._working_dir / input_path
        return input_path

    def _resolve_image_path(self, input_dir: Path, one_line_data: dict):
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
        """
        if PFBytes.is_multimedia_data(data_dict):
            for key in data_dict:
                format, resource = Image.get_multimedia_info(key)
                if resource == "path":
                    data_dict[key] = str(input_dir.parent / data_dict[key])
        return data_dict
        """
        for key in data_dict:
            if re.match(IMAGE_PATH_PATTERN, key):
                data_dict[key] = str(input_dir.parent / data_dict[key])
        return data_dict
