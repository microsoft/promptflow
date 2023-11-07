# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import hashlib
import json
from pathlib import Path
from typing import Dict

from promptflow._sdk._configuration import Configuration
from promptflow._sdk._constants import RecordMode
from promptflow._sdk._errors import RecordFileMissingException, RecordItemMissingException


class RecordStorage(object):
    """
    RecordStorage is used to store the record of node run.
    File often stored in .promptflow/node_cache.jsonl
    Currently only text input/output could be recorded.
    Example of cached items:
    {
        "/record/file/resolved": {
            "hash_value": { # hash_value is sha1 of dict, accelerate the search
                "input": {
                    "key1": "value1", # Converted to string, type info dropped
                },
                "output": "output_convert_to_string",
                "output_type": "output_type" # Currently support only simple strings.
            }
        }
    }
    """

    _standard_record_folder = ".promptflow"
    _standard_record_name = "node_cache.jsonl"
    _instance = None

    def __init__(self, record_file: str = None):
        """
        RecordStorage is used to store the record of node run.
        """
        self._record_file: Path = None
        self.cached_items: Dict[str, Dict[str, Dict[str, object]]] = {}
        self.record_file = record_file

    @property
    def record_file(self) -> Path:
        return self._record_file

    @record_file.setter
    def record_file(self, record_file) -> None:
        """
        Will load record_file if exist.
        """
        record_file_override = Configuration.get_instance().get_recording_file()
        if record_file is None and record_file_override is None:
            return

        # override record file
        if record_file_override is not None:
            record_file = record_file_override

        if record_file == self._record_file:
            return

        if isinstance(record_file, str):
            self._record_file = Path(record_file).resolve()
        elif isinstance(record_file, Path):
            self._record_file = record_file.resolve()
        else:
            return

        if not self._record_file.parts[-1].endswith(RecordStorage._standard_record_name):
            record_folder = self._record_file / RecordStorage._standard_record_folder
            self._record_file = record_folder / RecordStorage._standard_record_name
        else:
            record_folder = self._record_file.parent

        self._record_file_str = str(self._record_file)

        # cache folder we could create if not exist.
        if not record_folder.exists():
            record_folder.mkdir(parents=True, exist_ok=True)

        # if file exist, load file
        if self._record_file.exists():
            self._load_file()

    def _write_file(self) -> None:
        file_content = self.cached_items.get(self._record_file_str, None)

        if file_content is not None:
            with open(self.record_file, "w+", encoding="utf-8") as fp:
                for key, value in self.cached_items[self._record_file_str].items():
                    json.dump(value, fp, separators=(",", ":"), ensure_ascii=False)
                    fp.write("\n")

    def _load_file(self) -> None:
        local_content = self.cached_items.get(self._record_file_str, None)
        if not local_content:
            if not self.record_file.exists():
                return
            self.cached_items[self._record_file_str] = {}
            with open(self.record_file, "r", encoding="utf-8") as fp:
                json_list = list(fp)

            for json_str in json_list:
                json_dict = json.loads(json_str)
                input_dict = {}
                for key, value in json_dict["input"].items():
                    input_dict[key] = value
                hash_value = hashlib.sha1(str(sorted(input_dict)).encode("utf-8")).hexdigest()
                self.cached_items[self._record_file_str][hash_value] = json_dict

    def get_record(self, input_dict: Dict) -> object:
        """
        Get record from local storage.

        :param input_dict: input dict of critical AOAI inputs
        :type input_dict: Dict
        :raises RecordFileMissingException: Record file not exist
        :raises RecordItemMissingException: Record item not exist in record file
        :return: original output of node run
        :rtype: object
        """
        hash_value: str = hashlib.sha1(str(sorted(input_dict)).encode("utf-8")).hexdigest()
        current_saved_records: Dict[str, str] = self.cached_items.get(self._record_file_str, None)
        if current_saved_records is None:
            raise RecordFileMissingException(f"This should except earlier, record file not found {self.record_file}.")
        saved_output = current_saved_records.get(hash_value, None)
        if saved_output is None:
            raise RecordItemMissingException(
                f"Record item not found in file {self.record_file}.\n" f"values: {json.dumps(input_dict)}\n"
            )

        # not all items are reserved in the output dict.
        output = saved_output["output"]
        output_type = saved_output["output_type"]
        if isinstance(output, str) and output_type != "str":
            output_convert = json.loads(output)
            return output_convert
        else:
            return output

    def set_record(self, input_dict: Dict, output) -> None:
        """
        Set record to local storage, always override the old record.

        :param input_dict: input dict of critical AOAI inputs
        :type input_dict: OrderedDict
        :param output: original output of node run
        :type output: object
        """
        hash_value: str = hashlib.sha1(str(sorted(input_dict)).encode("utf-8")).hexdigest()
        current_saved_records: Dict[str, str] = self.cached_items.get(self._record_file_str, None)

        if current_saved_records is None:
            current_saved_records = {}
            current_saved_records[hash_value] = {
                "input": input_dict,
                "output": output,
                "output_type": type(output).__name__,
            }
        else:
            saved_output = current_saved_records.get(hash_value, None)
            if saved_output is not None:
                if saved_output["output"] == str(output) and saved_output["output_type"] == type(output).__name__:
                    return
                else:
                    current_saved_records[hash_value] = {
                        "input": input_dict,
                        "output": output,
                        "output_type": type(output).__name__,
                    }
            else:
                current_saved_records[hash_value] = {
                    "input": input_dict,
                    "output": str(output),
                    "output_type": type(output).__name__,
                }
        self.cached_items[self._record_file_str] = current_saved_records
        self._write_file()

    @classmethod
    def is_recording_mode(cls) -> bool:
        return Configuration.get_instance().get_recording_mode() == RecordMode.RECORD.value

    @classmethod
    def is_replaying_mode(cls) -> bool:
        return Configuration.get_instance().get_recording_mode() == RecordMode.REPLAY.value

    @classmethod
    def is_live_mode(cls) -> bool:
        return Configuration.get_instance().get_recording_mode() == RecordMode.LIVE.value

    @classmethod
    def get_instance(cls, record_file=None) -> "RecordStorage":
        """
        Use this to get instance to avoid multiple copies of same record storage.

        :param record_file: initiate at first entrance, defaults to None in the first call will raise exception.
        :type record_file: str or Path, optional
        :return: instance of RecordStorage
        :rtype: RecordStorage
        """
        # if not in recording mode, return None
        if not (RecordStorage.is_recording_mode() or RecordStorage.is_replaying_mode()):
            return None
        # Create instance if not exist
        if cls._instance is None:
            if record_file is None:
                raise RecordFileMissingException("record_file is value None")
            cls._instance = RecordStorage(record_file)
        if record_file is not None:
            cls._instance.record_file = record_file
        return cls._instance
