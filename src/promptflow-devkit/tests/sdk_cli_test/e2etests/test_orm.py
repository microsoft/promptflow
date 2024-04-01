# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import json
import uuid
from collections import namedtuple
from typing import Optional

import pytest

from promptflow._sdk._constants import ListViewType, RunStatus, RunTypes
from promptflow._sdk._errors import RunNotFoundError
from promptflow._sdk._orm import RunInfo
from promptflow._sdk._orm.trace import Event, LineRun, Span

SpanInfo = namedtuple("SpanInfo", ["trace_id", "span_id", "name"])


def persist_span(trace_id: str, span_id: str, name: str) -> None:
    span = Span(
        trace_id=trace_id,
        span_id=span_id,
        name=name,
        context={
            "trace_id": trace_id,
            "span_id": span_id,
            "trace_state": "",
        },
        kind="1",
        parent_id=None,
        start_time=datetime.datetime.now(),
        end_time=datetime.datetime.now(),
        status={
            "status_code": "Ok",
            "description": "",
        },
        attributes=None,
        links=None,
        events=None,
        resource={
            "attributes": {
                "service.name": "promptflow",
            },
            "schema_url": "",
        },
    )
    span.persist()


def persist_event(trace_id: str, span_id: str, event_id: Optional[str] = None) -> str:
    event_id = event_id or str(uuid.uuid4())
    event = Event(
        event_id=event_id,
        trace_id=trace_id,
        span_id=span_id,
        data=str(uuid.uuid4()),
    )
    event.persist()
    return event_id


def persist_line_run(
    trace_id: str,
    root_span_id: str,
    line_run_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    run: Optional[str] = None,
    line_number: Optional[int] = None,
) -> str:
    line_run_id = line_run_id or str(uuid.uuid4())
    line_run = LineRun(
        line_run_id=line_run_id,
        trace_id=trace_id,
        root_span_id=root_span_id,
        inputs=dict(),
        outputs=dict(),
        start_time=datetime.datetime.now(),
        end_time=datetime.datetime.now(),
        status="Ok",
        duration=3.14,
        name=str(uuid.uuid4()),
        kind="1",
        collection=str(uuid.uuid4()),
        parent_id=parent_id,
        run=run,
        line_number=line_number,
    )
    line_run.persist()
    return line_run_id


@pytest.fixture
def run_name() -> str:
    name = str(uuid.uuid4())
    run_info = RunInfo(
        name=name,
        type=RunTypes.BATCH,
        created_on=datetime.datetime.now().isoformat(),
        status=RunStatus.NOT_STARTED,
        display_name=name,
        description="",
        tags=None,
        properties=json.dumps({}),
    )
    run_info.dump()
    return name


@pytest.fixture
def mock_span() -> SpanInfo:
    trace_id = str(uuid.uuid4())
    span_id = str(uuid.uuid4())
    name = f"mock_span_{uuid.uuid4()}"
    persist_span(trace_id, span_id, name)
    return SpanInfo(trace_id=trace_id, span_id=span_id, name=name)


@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestRunInfo:
    def test_get(self, run_name: str) -> None:
        run_info = RunInfo.get(run_name)
        assert run_info.name == run_name
        assert run_info.type == RunTypes.BATCH
        assert run_info.status == RunStatus.NOT_STARTED
        assert run_info.display_name == run_name
        assert run_info.description == ""
        assert run_info.tags is None
        assert run_info.properties == json.dumps({})

    def test_get_not_exist(self) -> None:
        not_exist_name = str(uuid.uuid4())
        with pytest.raises(RunNotFoundError) as excinfo:
            RunInfo.get(not_exist_name)
        assert f"Run name {not_exist_name!r} cannot be found." in str(excinfo.value)

    def test_list_order_by_created_time_desc(self) -> None:
        for _ in range(3):
            RunInfo(
                name=str(uuid.uuid4()),
                created_on=datetime.datetime.now().isoformat(),
                status=RunStatus.NOT_STARTED,
                description="",
                tags=None,
                properties=json.dumps({}),
            ).dump()
        runs = RunInfo.list(max_results=3, list_view_type=ListViewType.ALL)
        # in very edge case, the created_on can be same, so use ">=" here
        assert runs[0].created_on >= runs[1].created_on >= runs[2].created_on

    def test_archive(self, run_name: str) -> None:
        run_info = RunInfo.get(run_name)
        assert run_info.archived is False
        run_info.archive()
        # in-memory archived flag
        assert run_info.archived is True
        # db archived flag
        assert RunInfo.get(run_name).archived is True

    def test_restore(self, run_name: str) -> None:
        run_info = RunInfo.get(run_name)
        run_info.archive()
        run_info = RunInfo.get(run_name)
        assert run_info.archived is True
        run_info.restore()
        # in-memory archived flag
        assert run_info.archived is False
        # db archived flag
        assert RunInfo.get(run_name).archived is False

    def test_update(self, run_name: str) -> None:
        run_info = RunInfo.get(run_name)
        assert run_info.status == RunStatus.NOT_STARTED
        assert run_info.display_name == run_name
        assert run_info.description == ""
        assert run_info.tags is None
        updated_status = RunStatus.COMPLETED
        updated_display_name = f"updated_{run_name}"
        updated_description = "updated_description"
        updated_tags = [{"key1": "value1", "key2": "value2"}]
        run_info.update(
            status=updated_status,
            display_name=updated_display_name,
            description=updated_description,
            tags=updated_tags,
        )
        # in-memory status, display_name, description and tags
        assert run_info.status == updated_status
        assert run_info.display_name == updated_display_name
        assert run_info.description == updated_description
        assert run_info.tags == json.dumps(updated_tags)
        # db status, display_name, description and tags
        run_info = RunInfo.get(run_name)
        assert run_info.status == updated_status
        assert run_info.display_name == updated_display_name
        assert run_info.description == updated_description
        assert run_info.tags == json.dumps(updated_tags)

    def test_null_type_and_display_name(self) -> None:
        # test run_info table schema change:
        # 1. type can be null(we will deprecate this concept in the future)
        # 2. display_name can be null as default value
        name = str(uuid.uuid4())
        run_info = RunInfo(
            name=name,
            created_on=datetime.datetime.now().isoformat(),
            status=RunStatus.NOT_STARTED,
            description="",
            tags=None,
            properties=json.dumps({}),
        )
        run_info.dump()
        run_info_from_db = RunInfo.get(name)
        assert run_info_from_db.type is None
        assert run_info_from_db.display_name is None


@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestTrace:
    def test_span_persist_and_get(self, mock_span: SpanInfo) -> None:
        span = Span.get(span_id=mock_span.span_id)
        assert span.name == mock_span.name
        span = Span.get(trace_id=mock_span.trace_id, span_id=mock_span.span_id)
        assert span.name == mock_span.name

    def test_span_list(self, mock_span: SpanInfo) -> None:
        spans = Span.list(trace_ids=mock_span.trace_id)
        assert len(spans) == 1

    def test_event_persist_and_get(self) -> None:
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        event_id = persist_event(trace_id=trace_id, span_id=span_id)
        event = Event.get(event_id=event_id)
        assert event.trace_id == trace_id and event.span_id == span_id

    def test_event_list(self) -> None:
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        persist_event(trace_id=trace_id, span_id=span_id)
        events = Event.list(trace_id=trace_id, span_id=span_id)
        assert len(events) == 1

    def test_line_run_persist_and_get(self) -> None:
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        line_run_id = persist_line_run(trace_id=trace_id, root_span_id=span_id)
        line_run = LineRun.get(line_run_id=line_run_id)
        assert line_run.trace_id == trace_id and line_run.root_span_id == span_id

    def test_line_run_children_get(self) -> None:
        # mock parent line run
        trace_id, span_id = str(uuid.uuid4()), str(uuid.uuid4())
        line_run_id = persist_line_run(trace_id=trace_id, root_span_id=span_id)
        # mock child line runs
        num_child_line_runs = 3
        child_line_run_ids = list()
        for _ in range(num_child_line_runs):
            child_line_run_id = persist_line_run(
                trace_id=str(uuid.uuid4()), root_span_id=str(uuid.uuid4()), parent_id=line_run_id
            )
            child_line_run_ids.append(child_line_run_id)
        child_line_runs = LineRun._get_children(line_run_id=line_run_id)
        assert len(child_line_runs) == num_child_line_runs
        for child_line_run in child_line_runs:
            assert child_line_run.line_run_id in child_line_run_ids
