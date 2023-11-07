# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import pandas as pd

from promptflow._constants import PROMPT_FLOW_DIR_NAME
from promptflow._utils.multimedia_utils import resolve_multimedia_data_recursively
from promptflow.exceptions import ErrorTarget, UserErrorException

module_logger = logging.getLogger(__name__)


def _pd_read_file(local_path: str, logger: logging.Logger = None, *, enable_parse_image_path=False) -> pd.DataFrame:
    local_path = str(local_path)
    # if file is empty, return empty DataFrame directly
    if (
        os.path.getsize(local_path) == 0
    ):  # CodeQL [SM01305] Safe use per local_path is set by PRT service not by end user
        return pd.DataFrame()
    # load different file formats

    # set dtype to object to avoid auto type conversion
    # executor will apply type conversion based on flow definition, so no conversion should be acceptable
    # note that for csv and tsv format, this will make integer and float columns to be string;
    # for rest, integer will be int and float will be float
    dtype = object
    # Only json data can determine whether it contains multimedia dict
    is_json_data = False

    if local_path.endswith(".csv"):
        df = pd.read_csv(local_path, dtype=dtype, keep_default_na=False)
    elif local_path.endswith(".json"):
        df = pd.read_json(local_path, dtype=dtype)
        is_json_data = True
    elif local_path.endswith(".jsonl"):
        df = pd.read_json(local_path, dtype=dtype, lines=True)
        is_json_data = True
    elif local_path.endswith(".tsv"):
        df = pd.read_table(local_path, dtype=dtype, keep_default_na=False)
    elif local_path.endswith(".parquet"):
        df = pd.read_parquet(local_path)  # read_parquet has no parameter dtype
    else:
        # parse file as jsonl when extension is not known (including unavailable)
        # ignore and logging if failed to load file content.
        try:
            df = pd.read_json(local_path, dtype=dtype, lines=True)
        except:  # noqa: E722
            if logger is None:
                logger = module_logger
            logger.warning(
                f"File {Path(local_path).name} is not supported format: "
                f"csv, tsv, json, jsonl, parquet. Ignoring it."
            )
            return pd.DataFrame()

    # Parse the image path into absolute path for flow consumption
    if is_json_data and enable_parse_image_path:
        for index, row in df.iterrows():
            for column_name, value in row.iteritems():
                local_path = Path(local_path).resolve()
                df.at[index, column_name] = resolve_multimedia_data_recursively(local_path, value)
    return df


def _bfs_dir(dir_path: List[str]) -> Tuple[List[str], List[str]]:
    """BFS traverse directory with depth 1, returns files and directories"""
    files, dirs = [], []
    for path in dir_path:
        # Ignore the json file under .promptflow folder
        if Path(path).name == PROMPT_FLOW_DIR_NAME:
            continue
        for filename in os.listdir(path):
            file = Path(path, filename).resolve()
            if file.is_file():
                files.append(str(file))
            else:
                dirs.append(str(file))
    return files, dirs


def _handle_dir(
    dir_path: str, max_rows_count: int, logger: logging.Logger = None, *, enable_parse_image_path=False
) -> pd.DataFrame:
    """load data from directory"""
    df = pd.DataFrame()

    # BFS traverse directory to collect files to load
    target_dir = [str(dir_path)]
    while len(target_dir) > 0:
        files, dirs = _bfs_dir(target_dir)
        for file in files:
            current_df = _pd_read_file(file, logger=logger, enable_parse_image_path=enable_parse_image_path)
            df = pd.concat([df, current_df])
        length = len(df)
        if max_rows_count and length > 0:
            if length > max_rows_count:
                df = df.head(max_rows_count)
            break
        # no readable data in current level, dive into next level
        target_dir = dirs
    return df


def load_data(
    local_path: Union[str, Path],
    *,
    logger: logging.Logger = None,
    max_rows_count: int = None,
    enable_parse_image_path=False,
) -> List[Dict[str, Any]]:
    """load data from local file"""
    df = load_df(local_path, logger, max_rows_count=max_rows_count, enable_parse_image_path=enable_parse_image_path)

    # convert dataframe to list of dict
    result = []
    for _, row in df.iterrows():
        result.append(row.to_dict())
    return result


def load_df(
    local_path: Union[str, Path],
    logger: logging.Logger = None,
    max_rows_count: int = None,
    *,
    enable_parse_image_path=False,
) -> pd.DataFrame:
    """load data from local file to df. For the usage of PRS."""
    lp = local_path if isinstance(local_path, Path) else Path(local_path)
    try:
        if lp.is_file():
            df = _pd_read_file(local_path, logger=logger, enable_parse_image_path=enable_parse_image_path)
            # honor max_rows_count if it is specified
            if max_rows_count and len(df) > max_rows_count:
                df = df.head(max_rows_count)
        else:
            df = _handle_dir(
                local_path,
                max_rows_count=max_rows_count,
                logger=logger,
                enable_parse_image_path=enable_parse_image_path,
            )
    except ValueError as e:
        raise InvalidUserData(
            message_format="Fail to load invalid data. We support file formats: csv, tsv, json, jsonl, parquet. "
            "Please check input data."
        ) from e

    return df


class InvalidUserData(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)
