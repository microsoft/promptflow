import datetime
import json
import typing
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from mock import mock

from promptflow._constants import RUNNING_LINE_RUN_STATUS, SPAN_EVENTS_ATTRIBUTES_EVENT_ID
from promptflow._sdk._constants import TRACE_DEFAULT_COLLECTION
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk.entities._trace import Span

TEST_ROOT = Path(__file__).parent.parent.parent
FLOWS_DIR = (TEST_ROOT / "test_configs/flows").resolve().absolute().as_posix()


def load_and_override_span_example(
    trace_id: str,
    span_id: str,
    parent_id: typing.Optional[str],
    line_run_id: str,
) -> typing.Dict:
    # load template span from local example file
    example_span_path = TEST_ROOT / "test_configs/traces/large-data-span-example.json"
    with open(example_span_path, mode="r", encoding="utf-8") as f:
        span_dict = json.load(f)
    # override field(s)
    span_dict["context"]["trace_id"] = trace_id
    span_dict["context"]["span_id"] = span_id
    span_dict["parent_id"] = parent_id
    span_dict["attributes"]["line_run_id"] = line_run_id
    return span_dict


def mock_span(
    trace_id: str,
    span_id: str,
    parent_id: typing.Optional[str],
    line_run_id: str,
) -> Span:
    span_dict = load_and_override_span_example(
        trace_id=trace_id, span_id=span_id, parent_id=parent_id, line_run_id=line_run_id
    )
    # type conversion for timestamp - required for Span constructor
    span_dict["start_time"] = datetime.datetime.fromisoformat(span_dict["start_time"])
    span_dict["end_time"] = datetime.datetime.fromisoformat(span_dict["end_time"])
    # create Span object
    return Span(
        name=span_dict["name"],
        trace_id=trace_id,
        span_id=span_id,
        parent_id=parent_id,
        context=span_dict["context"],
        kind=span_dict["kind"],
        start_time=span_dict["start_time"],
        end_time=span_dict["end_time"],
        status=span_dict["status"],
        attributes=span_dict["attributes"],
        links=span_dict["links"],
        events=span_dict["events"],
        resource=span_dict["resource"],
    )


@pytest.mark.e2etest
@pytest.mark.sdk_test
class TestTraceEntitiesAndOperations:
    def test_span_persist_and_gets(self, pf: PFClient) -> None:
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        parent_id = str(uuid.uuid4())
        line_run_id = str(uuid.uuid4())
        span = mock_span(trace_id=trace_id, span_id=span_id, parent_id=parent_id, line_run_id=line_run_id)
        span._persist()
        # trace operations - get span
        # eager load
        eager_load_span = pf._traces.get_span(trace_id=trace_id, span_id=span_id, lazy_load=False)
        expected_span_dict = load_and_override_span_example(
            trace_id=trace_id, span_id=span_id, parent_id=parent_id, line_run_id=line_run_id
        )
        assert eager_load_span._to_rest_object() == expected_span_dict
        # lazy load (default)
        lazy_load_span = pf._traces.get_span(trace_id=trace_id, span_id=span_id)
        lazy_load_rest_obj = lazy_load_span._to_rest_object()
        # without events, REST object should be the same as expected
        expected_span_dict.pop("events")
        lazy_load_events = lazy_load_rest_obj.pop("events")
        assert lazy_load_rest_obj == expected_span_dict
        for event in lazy_load_events:
            assert SPAN_EVENTS_ATTRIBUTES_EVENT_ID in event["attributes"]

    def test_spans_persist_and_line_run_get(self, pf: PFClient) -> None:
        trace_id = str(uuid.uuid4())
        non_root_span_id = str(uuid.uuid4())
        root_span_id = str(uuid.uuid4())
        line_run_id = str(uuid.uuid4())
        # non-root span
        span = mock_span(
            trace_id=trace_id,
            span_id=non_root_span_id,
            parent_id=root_span_id,
            line_run_id=line_run_id,
        )
        span._persist()
        running_line_run = pf._traces.get_line_run(line_run_id=line_run_id)
        expected_running_line_run_dict = {
            "line_run_id": line_run_id,
            "trace_id": trace_id,
            "root_span_id": None,
            "inputs": None,
            "outputs": None,
            "start_time": "2024-03-21T06:37:22.332582",
            "end_time": None,
            "status": RUNNING_LINE_RUN_STATUS,
            "duration": None,
            "name": None,
            "kind": None,
            "collection": TRACE_DEFAULT_COLLECTION,
            "cumulative_token_count": None,
            "parent_id": None,
            "run": None,
            "line_number": None,
            "experiment": None,
            "session_id": None,
            "evaluations": None,
        }
        assert running_line_run._to_rest_object() == expected_running_line_run_dict
        # root span
        span = mock_span(
            trace_id=trace_id,
            span_id=root_span_id,
            parent_id=None,
            line_run_id=line_run_id,
        )
        span._persist()
        terminated_line_run = pf._traces.get_line_run(line_run_id=line_run_id)
        expected_terminated_line_run_dict = {
            "line_run_id": line_run_id,
            "trace_id": trace_id,
            "root_span_id": root_span_id,
            "inputs": {"input1": "value1", "input2": "value2"},
            "outputs": {"output1": "val1", "output2": "val2"},
            "start_time": "2024-03-21T06:37:22.332582",
            "end_time": "2024-03-21T06:37:26.445007",
            "status": "Ok",
            "duration": 4.112425,
            "name": "openai.resources.chat.completions.Completions.create",
            "kind": "LLM",
            "collection": TRACE_DEFAULT_COLLECTION,
            "cumulative_token_count": {
                "completion": 14,
                "prompt": 1497,
                "total": 1511,
            },
            "parent_id": None,
            "run": None,
            "line_number": None,
            "experiment": None,
            "session_id": None,
            "evaluations": None,
        }
        assert terminated_line_run._to_rest_object() == expected_terminated_line_run_dict


@pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
@pytest.mark.e2etest
@pytest.mark.sdk_test
class TestTraceWithDevKit:
    def test_flow_test_trace_enabled(self, pf: PFClient) -> None:
        import promptflow.tracing._start_trace

        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            with patch.object(promptflow.tracing._start_trace, "start_trace") as mock_start_trace:
                inputs = {"url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g", "answer": "Channel", "evidence": "Url"}
                pf.test(flow=Path(f"{FLOWS_DIR}/web_classification").absolute(), inputs=inputs)
                assert mock_start_trace.call_count == 1

    def test_flow_test_single_node_trace_not_enabled(self, pf: PFClient) -> None:
        import promptflow.tracing._start_trace

        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            with patch.object(promptflow.tracing._start_trace, "start_trace") as mock_start_trace:
                pf.test(
                    flow=Path(f"{FLOWS_DIR}/web_classification").absolute(),
                    inputs={"fetch_url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g"},
                    node="fetch_text_content_from_url",
                )
                assert mock_start_trace.call_count == 0
