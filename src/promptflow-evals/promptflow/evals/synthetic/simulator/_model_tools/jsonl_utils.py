# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import logging
import pathlib
import tempfile
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def load_jsonl(file_path: pathlib.Path, source_encoding: str) -> List[Dict[str, Any]]:
    result = []
    logger.info("Loading JSON file: %s", file_path)
    with open(file_path, "r", encoding=source_encoding) as jlf:
        current_line = 0
        for line in jlf:
            logger.info("Processing line: %s", current_line)
            nxt = json.loads(line)
            result.append(nxt)
            current_line += 1
    return result


def save_jsonl(file_path: pathlib.Path, data: List[Dict[str, Any]], destination_encoding: str):
    logger.info("Saving file %s", file_path)
    with open(file_path, "w", encoding=destination_encoding) as out_file:
        for i, d in enumerate(data):
            logger.info("Writing element %s", i)
            d_str = json.dumps(d)
            out_file.write(d_str)
            out_file.write("\n")


def line_map(
    *,
    map_func: Callable[[Dict[str, Any]], Dict[str, Any]],
    source_file: pathlib.Path,
    dest_file: pathlib.Path,
    source_encoding: str,
    dest_encoding: str,
    error_file: Optional[pathlib.Path] = None,
    error_encoding: Optional[str] = None,
) -> Tuple[int, int]:
    """
    Iterate over a JSONL file, applying map_func to each line

    :return: A tuple containing the number of lines processed and the number of lines successfully mapped.
    :rtype: Tuple[int, int]
    """
    assert source_file.exists()

    # If error_file is not specified, set up a temporary file
    def get_error_file(error_file_path: Optional[pathlib.Path]):
        if error_file_path:
            return open(error_file_path, "a", encoding=error_encoding)
        return tempfile.TemporaryFile(mode="w", encoding="utf-8-sig")

    successful_lines = 0
    error_lines = 0
    with open(source_file, "r", encoding=source_encoding) as in_file:
        with open(dest_file, "w", encoding=dest_encoding) as out_file:
            with get_error_file(error_file) as err_file:
                current_line = 0
                for nxt in in_file:
                    logger.info("Processing line: %s", current_line)
                    nxt_dict = json.loads(nxt)
                    try:
                        nxt_output = map_func(nxt_dict)
                        nxt_output_string = json.dumps(nxt_output)
                        logger.info("Writing output: %s", nxt_output_string)
                        out_file.write(nxt_output_string)
                        out_file.write("\n")
                        successful_lines += 1
                    except IOError as e:
                        logger.warning("Caught exception: %s", e)
                        err_file.write(nxt)
                        error_lines += 1
                    current_line += 1
    logger.info("line_map complete (%s successes, %s failures)", successful_lines, error_lines)
    return successful_lines, error_lines
