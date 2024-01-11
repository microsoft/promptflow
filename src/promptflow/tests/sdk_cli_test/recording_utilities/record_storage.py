# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import hashlib
import json
import os
import shelve
from pathlib import Path
from typing import Dict

from filelock import FileLock

from promptflow.exceptions import PromptflowException
from .constants import ENVIRON_TEST_MODE, RecordMode


class RecordItemMissingException(PromptflowException):
    """Exception raised when record item missing."""

    pass


class RecordFileMissingException(PromptflowException):
    """Exception raised when record file missing or invalid."""

    pass


class RecordStorage(object):
    """
    RecordStorage is used to store the record of node run.
    File often stored in .promptflow/node_cache.shelve
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
    _standard_record_name = "node_cache.shelve"
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
    def record_file(self, record_file_input) -> None:
        """
        Will load record_file if exist.
        """
        if record_file_input == self._record_file:
            return

        if isinstance(record_file_input, str):
            self._record_file = Path(record_file_input).resolve()
        elif isinstance(record_file_input, Path):
            self._record_file = record_file_input.resolve()
        else:
            return

        if not self._record_file.parts[-1].endswith(RecordStorage._standard_record_name):
            record_folder = self._record_file / RecordStorage._standard_record_folder
            self._record_file = record_folder / RecordStorage._standard_record_name
        else:
            record_folder = self._record_file.parent

        self._record_file_str = str(self._record_file.resolve())

        # cache folder we could create if not exist.
        if not record_folder.exists():
            record_folder.mkdir(parents=True, exist_ok=True)

        # if file exist, load file
        if self.exists_record_file(record_folder, self._record_file.parts[-1]):
            self._load_file()
        else:
            self.cached_items = {
                self._record_file_str: {},
            }

    def exists_record_file(self, record_folder, file_name) -> bool:
        files = os.listdir(record_folder)
        for file in files:
            if file.startswith(file_name):
                return True
        return False

    def _write_file(self, hashkey) -> None:
        file_content = self.cached_items.get(self._record_file_str, None)

        if file_content is not None:
            file_content_line = file_content.get(hashkey, None)
            if file_content_line is not None:
                lock = FileLock(self.record_file.parent / "record_file.lock")
                with lock:
                    saved_dict = shelve.open(self._record_file_str, "c", writeback=False)
                    saved_dict[hashkey] = file_content_line
                    saved_dict.close()
            else:
                raise RecordItemMissingException(f"Record item not found in cache with hashkey {hashkey}.")
        else:
            raise RecordFileMissingException(
                f"This exception should not happen here, but record file is not found {self._record_file_str}."
            )

    def _load_file(self) -> None:
        local_content = self.cached_items.get(self._record_file_str, None)
        if not local_content:
            if RecordStorage.is_recording_mode():
                lock = FileLock(self.record_file.parent / "record_file.lock")
                with lock:
                    if not self.exists_record_file(self.record_file.parent, self.record_file.parts[-1]):
                        return
                    self.cached_items[self._record_file_str] = {}
                    saved_dict = shelve.open(self._record_file_str, "r", writeback=False)
                    for key, value in saved_dict.items():
                        self.cached_items[self._record_file_str][key] = value
                    saved_dict.close()
            else:
                if not self.exists_record_file(self.record_file.parent, self.record_file.parts[-1]):
                    return
                self.cached_items[self._record_file_str] = {}
                saved_dict = shelve.open(self._record_file_str, "r", writeback=False)
                for key, value in saved_dict.items():
                    self.cached_items[self._record_file_str][key] = value
                saved_dict.close()

    def delete_lock_file(self):
        lock_file = self.record_file.parent / "record_file.lock"
        if lock_file.exists():
            os.remove(lock_file)

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
        input_dict = self._recursive_create_hashable_args(input_dict)
        hash_value: str = hashlib.sha1(str(sorted(input_dict.items())).encode("utf-8")).hexdigest()
        current_saved_records: Dict[str, str] = self.cached_items.get(self._record_file_str, None)
        if current_saved_records is None:
            raise RecordFileMissingException(f"Record file not found {self.record_file}.")
        saved_output = current_saved_records.get(hash_value, None)
        if saved_output is None:
            raise RecordItemMissingException(
                f"Record item not found in file {self.record_file}.\n" f"values: {json.dumps(input_dict)}\n"
            )

        # not all items are reserved in the output dict.
        output = saved_output["output"]
        output_type = saved_output["output_type"]
        if "generator" in output_type:
            return self._create_output_generator(output, output_type)
        else:
            return output

    def _recursive_create_hashable_args(self, item):
        if isinstance(item, tuple):
            return [self._recursive_create_hashable_args(i) for i in item]
        if isinstance(item, list):
            return [self._recursive_create_hashable_args(i) for i in item]
        if isinstance(item, dict):
            return {k: self._recursive_create_hashable_args(v) for k, v in item.items()}
        elif "module: promptflow.connections" in str(item) or "object at" in str(item):
            return []
        else:
            return item

    def _parse_output_generator(self, output):
        """
        Special handling for generator type. Since pickle will not work for generator.
        Returns the real list for reocrding, and create a generator for original output.
        Parse output has a simplified hypothesis: output is simple dict, list or generator,
        because a full schema of output is too heavy to handle.
        Example: {"answer": <generator>, "a": "b"}, <generator>
        """
        output_type = ""
        output_value = None
        output_generator = None
        if isinstance(output, dict):
            output_value = {}
            output_generator = {}
            for item in output.items():
                k, v = item
                if type(v).__name__ == "generator":
                    vlist = list(v)

                    def vgenerator():
                        for vitem in vlist:
                            yield vitem

                    output_value[k] = vlist
                    output_generator[k] = vgenerator()
                    output_type = "dict[generator]"
                else:
                    output_value[k] = v
        elif type(output).__name__ == "generator":
            output_value = list(output)

            def generator():
                for item in output_value:
                    yield item

            output_generator = generator()
            output_type = "generator"
        else:
            output_value = output
            output_generator = None
            output_type = type(output).__name__
        return output_value, output_generator, output_type

    def _create_output_generator(self, output, output_type):
        """
        Special handling for generator type.
        Returns a generator for original output.
        Create output has a simplified hypothesis:
        All list with output type generator is treated as generator.
        """
        output_generator = None
        if output_type == "dict[generator]":
            output_generator = {}
            for k, v in output.items():
                if type(v).__name__ == "list":

                    def vgenerator():
                        for item in v:
                            yield item

                    output_generator[k] = vgenerator()
                else:
                    output_generator[k] = v
        elif output_type == "generator":

            def generator():
                for item in output:
                    yield item

            output_generator = generator()
        return output_generator

    def set_record(self, input_dict: Dict, output):
        """
        Set record to local storage, always override the old record.

        :param input_dict: input dict of critical AOAI inputs
        :type input_dict: OrderedDict
        :param output: original output of node run
        :type output: object
        """
        # filter args, object at will not hash
        input_dict = self._recursive_create_hashable_args(input_dict)
        hash_value: str = hashlib.sha1(str(sorted(input_dict.items())).encode("utf-8")).hexdigest()
        current_saved_records: Dict[str, str] = self.cached_items.get(self._record_file_str, None)
        output_value, output_generator, output_type = self._parse_output_generator(output)

        if current_saved_records is None:
            current_saved_records = {}
            current_saved_records[hash_value] = {
                "input": input_dict,
                "output": output_value,
                "output_type": output_type,
            }
        else:
            saved_output = current_saved_records.get(hash_value, None)
            if saved_output is not None:
                if saved_output["output"] == output_value and saved_output["output_type"] == output_type:
                    if "generator" in output_type:
                        return output_generator
                    else:
                        return output_value
                else:
                    current_saved_records[hash_value] = {
                        "input": input_dict,
                        "output": output_value,
                        "output_type": output_type,
                    }
            else:
                current_saved_records[hash_value] = {
                    "input": input_dict,
                    "output": output_value,
                    "output_type": output_type,
                }
        self.cached_items[self._record_file_str] = current_saved_records
        self._write_file(hash_value)
        if "generator" in output_type:
            return output_generator
        else:
            return output_value

    @classmethod
    def get_test_mode_from_environ(cls) -> str:
        return os.getenv(ENVIRON_TEST_MODE, RecordMode.LIVE)

    @classmethod
    def is_recording_mode(cls) -> bool:
        return RecordStorage.get_test_mode_from_environ() == RecordMode.RECORD

    @classmethod
    def is_replaying_mode(cls) -> bool:
        return RecordStorage.get_test_mode_from_environ() == RecordMode.REPLAY

    @classmethod
    def is_live_mode(cls) -> bool:
        return RecordStorage.get_test_mode_from_environ() == RecordMode.LIVE

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
