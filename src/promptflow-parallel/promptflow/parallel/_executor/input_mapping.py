# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Iterator

from promptflow._utils.multimedia_utils import resolve_multimedia_data_recursively
from promptflow.executor import FlowExecutor
from promptflow.parallel._model import Row


class InputMapping:
    def __init__(self, input_dir: Path, side_input_dir: Path, mapping: Dict[str, str]):
        self._input_dir = input_dir
        self._side_input_dir = side_input_dir
        self._mapping = mapping
        self._logger = logging.getLogger(self.__class__.__name__)
        self._loading = self._start_load()

    def is_enabled(self):
        return self._mapping and True

    def apply(self, row: Row) -> Row:
        if not self.is_enabled():
            return row
        mapping_inputs = {"data": row}
        if self._rows:
            side_input = self._rows.get(row.row_number, None)
            if side_input:
                mapping_inputs["run.outputs"] = side_input
            else:
                self._logger.warning(f"Could not find run output for row {row.row_number}")
        mapped = FlowExecutor.apply_inputs_mapping(inputs=mapping_inputs, inputs_mapping=self._mapping)
        self._resolve_image_path(mapped)
        return Row.from_dict(mapped, row.row_number)

    def _resolve_image_path(self, mapped_row: Dict[str, Any]) -> None:
        for k, v in mapped_row.items():
            mapped_row[k] = resolve_multimedia_data_recursively(self._input_dir, v)

    @property
    def _rows(self) -> Dict[int, Row]:
        return self._loading.result()

    def _start_load(self) -> Future:
        if self.is_enabled():
            return ThreadPoolExecutor(max_workers=1).submit(self._load)
        f = Future()
        f.set_result({})
        return f

    def _load(self):
        self._logger.info(f"Loading rows from side input: {self._side_input_dir}.")
        result = {}
        for index, json_str in enumerate(self._read_from_folder(self._side_input_dir)):
            row = Row.from_json(json_str, row_number=index)
            result[row.row_number] = row
        self._logger.info(f"Loaded {len(result)} rows from side input.")
        return result

    def _read_from_folder(self, folder: Path) -> Iterator[str]:
        if folder is None or not folder.exists():
            return

        for p in folder.iterdir():
            if p.is_dir():
                continue
            self._logger.info(f"Reading file {p}")
            with open(p, "r") as f:
                for line in f:
                    yield line
