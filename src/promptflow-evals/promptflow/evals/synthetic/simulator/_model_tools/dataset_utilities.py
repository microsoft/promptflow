# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os
from glob import glob
from typing import Any, Iterator, Tuple


def jsonl_file_iter(filepath: str) -> Iterator[Tuple[int, dict]]:
    """
    Generate pool data from filepath, used to load from file iteratively.

    :param filepath: The path to the JSONL file.
    :type filepath: str
    :return: An iterator yielding tuples containing an integer identifier and a dictionary of data.
    :rtype: Iterator[Tuple[int, dict]]
    """
    with open(filepath, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if line.strip():
                yield idx, json.loads(line)


def resolve_file(dataset: str, filename: str) -> str:
    """
    Resolve a file from a dataset and filename and assert only one file is found.

    :param dataset: The dataset name.
    :type dataset: str
    :param filename: The name of the file to resolve.
    :type filename: str
    :return: The resolved file path.
    :rtype: str
    """
    if os.path.isfile(dataset):
        filenames = glob(dataset)
    else:
        path = os.path.join(dataset, filename)
        path = os.path.abspath(path)
        filenames = glob(path)
    assert len(filenames) == 1, f"Expected 1 file for {filename}, found {len(filenames)}: {filenames} in {path}"
    return filenames[0]


def batched_iterator(iterator: Iterator[Any], batch_size: int) -> Iterator[Any]:
    """
    Batch an iterator into a new iterator.

    :param iterator: The input iterator to be batched.
    :type iterator: Iterator[Any]
    :param batch_size: The size of each batch.
    :type batch_size: int
    :return: An iterator yielding batches of elements from the input iterator.
    :rtype: Iterator[Any]
    """
    batch = []
    for item in iterator:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch
