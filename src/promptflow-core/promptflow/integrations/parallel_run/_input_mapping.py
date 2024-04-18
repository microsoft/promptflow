# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Iterator

from promptflow._utils.multimedia_utils import resolve_multimedia_data_recursively
from promptflow.executor import FlowExecutor
from promptflow.integrations.parallel_run._model import Row


class InputMapping:
    def __init__(self, input_dir: Path, side_input_dir: Path, mapping: Dict[str, str]):
        self._input_dir = input_dir
        self._side_input_dir = side_input_dir
        self._mapping = mapping
        self._loading = self._start_load()

    def apply(self, row: Row) -> Row:
        mapping_inputs = {"data": row}
        side_input = self._rows.get(row.row_number, None)
        if side_input:
            mapping_inputs["run.outputs"] = side_input
        else:
            print(f"Could not find run output for row {row.row_number}")
        mapped = FlowExecutor.apply_inputs_mapping(inputs=mapping_inputs, inputs_mapping=self._mapping)
        self._resolve_image_path(mapped)
        return Row.from_dict(mapped, row.row_number)

    def _resolve_image_path(self, mapped_row: Dict[str, Any]) -> None:
        for k, v in mapped_row:
            mapped_row[k] = resolve_multimedia_data_recursively(self._input_dir, v)

    @property
    def _rows(self) -> Dict[int, Row]:
        return self._loading.result()

    def _start_load(self) -> Future:
        return ThreadPoolExecutor(max_workers=1).submit(self._load)

    def _load(self):
        print("Loading rows...")
        result = {}
        for index, json_str in enumerate(self._read_from_folder(self._side_input_dir)):
            row = Row.from_json(json_str, line_number=index)
            result[row.row_number] = row
        return result

    @staticmethod
    def _read_from_folder(folder: Path) -> Iterator[str]:
        if folder is None or not folder.exists():
            return

        for p in folder.iterdir():
            if p.is_dir():
                continue
            print(f"Reading file {p}")
            with open(p, "r") as f:
                for line in f:
                    yield line
