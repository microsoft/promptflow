# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import collections
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, OrderedDict

from promptflow._sdk._configuration import Configuration
from promptflow._sdk._constants import RecordMode
from promptflow._sdk._errors import RecordFileMissingException, RecordItemMissingException
from promptflow._utils.dataclass_serializer import serialize
from promptflow._utils.tool_utils import get_inputs_for_prompt_template


class RecordStorage(object):
    """
    RecordStorage is used to store the record of node run.
    File often stored in .promptflow/node_cache.json
    Example of cached items:
    {
        "/record/file/resolved": {
            "hash_value": { # hash_value is sha1 of dict, accelerate the search
                "input": {
                    "key1": "value1", # Converted to string, type info dropped
                },
                "output": "output_convert_to_string",
                "output_type": "output_type" # Currently support only simple types.
            }
        }
    }
    """

    _standard_record_folder = ".promptflow"
    _standard_record_name = "node_cache.json"
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

        if self._record_file.parts[-1] != RecordStorage._standard_record_name:
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
                json.dump(self.cached_items[self._record_file_str], fp, indent=4)

    def _load_file(self) -> None:
        local_content = self.cached_items.get(self._record_file_str, None)
        if not local_content:
            if not self.record_file.exists():
                return
            with open(self.record_file, "r", encoding="utf-8") as fp:
                self.cached_items[self._record_file_str] = json.load(fp)

    def get_record(self, input_dict: OrderedDict) -> object:
        hash_value: str = hashlib.sha1(str(input_dict).encode("utf-8")).hexdigest()
        current_saved_records: Dict[str, str] = self.cached_items.get(self._record_file_str, None)
        if current_saved_records is None:
            raise RecordFileMissingException(
                f"This should except earlier, record file not found in folder {self.input_path}."
            )
        saved_output = current_saved_records.get(hash_value, None)
        if saved_output is None:
            raise RecordItemMissingException(
                f"Record item not found in folder {self.input_path}.\n" f"values: {json.dumps(input_dict)}\n"
            )

        output = saved_output["output"]
        output_type = saved_output["output_type"]
        if isinstance(output, str) and output_type != "str":
            output_convert = json.loads(output)
            return output_convert
        else:
            return output

    def set_record(self, input_dict: OrderedDict, output: object) -> None:
        hash_value: str = hashlib.sha1(str(input_dict).encode("utf-8")).hexdigest()
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
        return Configuration.get_instance().get_recording_mode() == RecordMode.RECORD

    @classmethod
    def is_replaying_mode(cls) -> bool:
        return Configuration.get_instance().get_recording_mode() == RecordMode.REPLAY

    @classmethod
    def is_live_mode(cls) -> bool:
        return Configuration.get_instance().get_recording_mode() == RecordMode.LIVE

    @classmethod
    def get_instance(cls, record_file=None) -> "RecordStorage":
        """
        get_instance Use this to get instance to avoid multiple copies of same record storage.

        :param input_path: initiate at first entrance, defaults to None in the first call will raise exception.
        :type input_path: str or Path, optional
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
        cls._instance.record_file = record_file
        return cls._instance

    def _record_node_run(self, run_info, api_call: Dict[str, Any]) -> None:
        hashDict = {}
        # current
        if "name" in api_call and api_call["name"].startswith("AzureOpenAI"):
            prompt_tpl = api_call["inputs"]["prompt"]
            prompt_tpl_inputs = get_inputs_for_prompt_template(prompt_tpl)

            for keyword in prompt_tpl_inputs:
                if keyword in api_call["inputs"]:
                    hashDict[keyword] = api_call["inputs"][keyword]
            hashDict["prompt"] = prompt_tpl
            hashDict = collections.OrderedDict(sorted(hashDict.items()))
            item = serialize(run_info)
            self.set_record(hashDict, str(item["output"]))

    def record_node_run(self, run_info: Any) -> None:
        """Recording: Persist llm node run record to local storage."""
        if isinstance(run_info, dict):
            for api_call in run_info["api_calls"]:
                self._record_node_run(run_info, api_call)
        else:
            for api_call in run_info.api_calls:
                self._record_node_run(run_info, api_call)
