# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Tuple

import pytest

from promptflow.contracts.run_info import Status
from promptflow.parallel._processor.debug_info import DebugInfo
from promptflow.storage.run_records import LineRunRecord, NodeRunRecord


@pytest.fixture
def record():
    def create_record(line_number, node_count=2):
        return (
            create_line_run_record(line_number),
            [create_node_run_record(line_number, f"node_{i}") for i in range(1, node_count + 1)],
        )

    return create_record


def create_line_run_record(line_number, name="test"):
    return LineRunRecord(
        line_number=line_number,
        run_info={},
        start_time=(datetime.now() - timedelta(hours=1)).isoformat(),
        end_time=datetime.now().isoformat(),
        name=name,
        description=f"test line {line_number}",
        status=Status.Completed.value,
        tags="test_tag",
    )


def create_node_run_record(line_number, name):
    return NodeRunRecord(
        node_name=name,
        line_number=line_number,
        run_info={},
        start_time=(datetime.now() - timedelta(hours=1)).isoformat(),
        end_time=datetime.now().isoformat(),
        status=Status.Completed.value,
    )


def read_flow_debug_info(debug_info: DebugInfo) -> Iterable[Tuple[Path, LineRunRecord]]:
    for file in debug_info.flow_output_dir.iterdir():
        with file.open("r") as f:
            for line in f:
                yield file, LineRunRecord(**json.loads(line))


def read_node_debug_info(debug_info: DebugInfo) -> Iterable[Tuple[Path, NodeRunRecord]]:
    for node_dir in debug_info.node_output_dir("").iterdir():
        for file in node_dir.iterdir():
            with file.open("r") as f:
                for line in f:
                    yield file, NodeRunRecord(**json.loads(line))


def test_prepare():
    debug_info = DebugInfo.temporary()

    assert not debug_info.flow_output_dir.exists()
    assert not debug_info.node_output_dir("test").parent.exists()

    debug_info.prepare()

    assert debug_info.flow_output_dir.exists()
    assert debug_info.node_output_dir("test").parent.exists()


@pytest.fixture
def records_assertion(record):
    def assert_records_written(debug_info: DebugInfo, run_records: List[Tuple[LineRunRecord, List[NodeRunRecord]]]):
        line_run_records = list(read_flow_debug_info(debug_info))
        # 2 records are in the same file
        assert line_run_records[0][0] == line_run_records[1][0]
        # records are written in the order they are passed to the method
        assert line_run_records[0][1].line_number == run_records[0][0].line_number
        assert line_run_records[1][1].line_number == run_records[1][0].line_number

        node_run_records = list(read_node_debug_info(debug_info))
        assert len(node_run_records) == len(run_records[0][1]) + len(run_records[1][1])
        # file count = line_count_of_node_1 + ... + line_count_of_node_n
        assert len({r[0] for r in node_run_records}) == len(run_records[0][1]) + len(run_records[1][1])

    return [record(1, 2), record(2, 2)], assert_records_written


@pytest.mark.unittest
def test_write(records_assertion):
    debug_info = DebugInfo.temporary()
    debug_info.prepare()

    records, assert_records_written = records_assertion
    for line_run_record, node_run_records in records:
        debug_info.write(line_run_record, node_run_records)

    assert_records_written(debug_info, records)


@pytest.mark.unittest
def test_write_batch(records_assertion):
    debug_info = DebugInfo.temporary()
    debug_info.prepare()

    records, assert_records_written = records_assertion
    debug_info.write_batch(records)
    assert_records_written(debug_info, records)
