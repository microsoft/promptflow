import datetime
import json
import platform
import sys
import time
import typing
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from _constants import PROMPTFLOW_ROOT
from mock import mock

from promptflow._constants import (
    RUNNING_LINE_RUN_STATUS,
    SpanAttributeFieldName,
    SpanResourceAttributesFieldName,
    SpanResourceFieldName,
)
from promptflow._sdk._constants import TRACE_DEFAULT_COLLECTION
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk.entities._trace import Span
from promptflow.tracing import start_trace

TEST_ROOT = (PROMPTFLOW_ROOT / "tests").resolve().absolute()
FLOWS_DIR = (TEST_ROOT / "test_configs/flows").resolve().absolute().as_posix()
FLEX_FLOWS_DIR = (TEST_ROOT / "test_configs/eager_flows").resolve().absolute().as_posix()
PROMPTY_DIR = (TEST_ROOT / "test_configs/prompty").resolve().absolute().as_posix()
DATA_DIR = (TEST_ROOT / "test_configs/datas").resolve().absolute().as_posix()


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


def mock_span_for_delete_tests(
    run: typing.Optional[str] = None,
    collection: typing.Optional[str] = None,
    start_time: typing.Optional[datetime.datetime] = None,
) -> Span:
    span = mock_span(
        trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4()), parent_id=None, line_run_id=str(uuid.uuid4())
    )
    if run is not None:
        span.attributes.pop(SpanAttributeFieldName.LINE_RUN_ID)
        span.attributes[SpanAttributeFieldName.BATCH_RUN_ID] = run
        span.attributes[SpanAttributeFieldName.LINE_NUMBER] = 0  # always line 0
    if collection is not None:
        span.resource[SpanResourceFieldName.ATTRIBUTES][SpanResourceAttributesFieldName.COLLECTION] = collection
    if start_time is not None:
        span.start_time = start_time
    span._persist()
    return span


def assert_span_equals(span: Span, expected_span_dict: typing.Dict) -> None:
    span_dict = span._to_rest_object()
    # assert "external_event_data_uris" in span_dict and pop
    assert "external_event_data_uris" in span_dict
    span_dict.pop("external_event_data_uris")
    assert span_dict == expected_span_dict


@pytest.fixture
def collection() -> str:
    _collection = str(uuid.uuid4())
    start_trace(collection=_collection)
    return _collection


@pytest.mark.e2etest
@pytest.mark.sdk_test
class TestTraceEntitiesAndOperations:
    def test_span_to_dict(self) -> None:
        # this should be the groundtruth as OpenTelemetry span spec
        otel_span_path = TEST_ROOT / "test_configs/traces/large-data-span-example.json"
        with open(otel_span_path, mode="r", encoding="utf-8") as f:
            span_dict = json.load(f)
        span_entity = Span(
            name=span_dict["name"],
            trace_id=span_dict["context"]["trace_id"],
            span_id=span_dict["context"]["span_id"],
            parent_id=span_dict["parent_id"],
            context=span_dict["context"],
            kind=span_dict["kind"],
            start_time=datetime.datetime.fromisoformat(span_dict["start_time"]),
            end_time=datetime.datetime.fromisoformat(span_dict["end_time"]),
            status=span_dict["status"],
            attributes=span_dict["attributes"],
            links=span_dict["links"],
            events=span_dict["events"],
            resource=span_dict["resource"],
        )
        otel_span_dict = {
            "name": "openai.resources.chat.completions.Completions.create",
            "context": {
                "trace_id": "32a6fb50e281736543979ce5b929dfdc",
                "span_id": "3a3596a19efef900",
                "trace_state": "",
            },
            "kind": "1",
            "parent_id": "9c63581c6da66596",
            "start_time": "2024-03-21T06:37:22.332582Z",
            "end_time": "2024-03-21T06:37:26.445007Z",
            "status": {
                "status_code": "Ok",
                "description": "",
            },
            "attributes": {
                "framework": "promptflow",
                "span_type": "LLM",
                "function": "openai.resources.chat.completions.Completions.create",
                "node_name": "Azure_OpenAI_GPT_4_Turbo_with_Vision_mrr4",
                "line_run_id": "277fab99-d26e-4c43-8ec4-b0c61669fd68",
                "llm.response.model": "gpt-4",
                "__computed__.cumulative_token_count.completion": "14",
                "__computed__.cumulative_token_count.prompt": "1497",
                "__computed__.cumulative_token_count.total": "1511",
                "llm.usage.completion_tokens": "14",
                "llm.usage.prompt_tokens": "1497",
                "llm.usage.total_tokens": "1511",
            },
            "events": [
                {
                    "name": "promptflow.function.inputs",
                    "timestamp": "2024-03-21T06:37:22.332582Z",
                    "attributes": {
                        "payload": '{"input1": "value1", "input2": "value2"}',
                    },
                },
                {
                    "name": "promptflow.function.output",
                    "timestamp": "2024-03-21T06:37:26.445007Z",
                    "attributes": {
                        "payload": '{"output1": "val1", "output2": "val2"}',
                    },
                },
            ],
            "links": [],
            "resource": {
                "attributes": {
                    "service.name": "promptflow",
                    "collection": "default",
                },
                "schema_url": "",
            },
        }
        assert span_entity.to_dict() == otel_span_dict

    def test_span_persist_and_gets(self, pf: PFClient) -> None:
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        parent_id = str(uuid.uuid4())
        line_run_id = str(uuid.uuid4())
        span = mock_span(trace_id=trace_id, span_id=span_id, parent_id=parent_id, line_run_id=line_run_id)
        span._persist()
        # trace operations - get span
        # eager load
        eager_load_span = pf.traces.get_span(trace_id=trace_id, span_id=span_id, lazy_load=False)
        expected_span_dict = load_and_override_span_example(
            trace_id=trace_id, span_id=span_id, parent_id=parent_id, line_run_id=line_run_id
        )
        assert_span_equals(eager_load_span, expected_span_dict)
        # lazy load (default)
        lazy_load_span = pf.traces.get_span(trace_id=trace_id, span_id=span_id)
        # events.attributes should be empty in lazy load mode
        for i in range(len(expected_span_dict["events"])):
            expected_span_dict["events"][i]["attributes"] = dict()
        assert_span_equals(lazy_load_span, expected_span_dict)

    def test_aggregation_node_in_eval_run(self, pf: PFClient) -> None:
        # mock a span generated from an aggregation node in an eval run
        # whose attributes has `referenced.batch_run_id`, no `line_number`
        span = mock_span(
            trace_id=str(uuid.uuid4()),
            span_id=str(uuid.uuid4()),
            parent_id=None,
            line_run_id=str(uuid.uuid4()),
        )
        batch_run_id = str(uuid.uuid4())
        span.attributes.pop(SpanAttributeFieldName.LINE_RUN_ID)
        span.attributes[SpanAttributeFieldName.BATCH_RUN_ID] = batch_run_id
        span.attributes[SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID] = str(uuid.uuid4())
        span._persist()
        # list and assert to ensure the persist is successful
        line_runs = pf.traces.list_line_runs(runs=[batch_run_id])
        assert len(line_runs) == 1

    def test_spans_persist_and_line_run_gets(self, pf: PFClient) -> None:
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
        running_line_run = pf.traces.get_line_run(line_run_id=line_run_id)
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
        terminated_line_run = pf.traces.get_line_run(line_run_id=line_run_id)
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

    def test_span_io_in_attrs_persist(self, pf: PFClient) -> None:
        trace_id, span_id, line_run_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        span = mock_span(trace_id=trace_id, span_id=span_id, parent_id=None, line_run_id=line_run_id)
        # empty span.events and move inputs/output to span.attributes
        inputs = {"input1": "value1", "input2": "value2"}
        output = {"output1": "val1", "output2": "val2"}
        span.attributes[SpanAttributeFieldName.INPUTS] = json.dumps(inputs)
        span.attributes[SpanAttributeFieldName.OUTPUT] = json.dumps(output)
        span.events = list()
        span._persist()
        line_run = pf.traces.get_line_run(line_run_id=line_run_id)
        assert line_run.inputs == inputs
        assert line_run.outputs == output

    def test_span_non_json_io_in_attrs_persist(self, pf: PFClient) -> None:
        trace_id, span_id, line_run_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        span = mock_span(trace_id=trace_id, span_id=span_id, parent_id=None, line_run_id=line_run_id)
        # empty span.events and set non-JSON inputs/output to span.attributes
        inputs = {"input1": "value1", "input2": "value2"}
        output = {"output1": "val1", "output2": "val2"}
        span.attributes[SpanAttributeFieldName.INPUTS] = str(inputs)
        span.attributes[SpanAttributeFieldName.OUTPUT] = str(output)
        span.events = list()
        span._persist()
        line_run = pf.traces.get_line_run(line_run_id=line_run_id)
        assert isinstance(line_run.inputs, str) and line_run.inputs == str(inputs)
        assert isinstance(line_run.outputs, str) and line_run.outputs == str(output)

    def test_span_with_nan_as_io(self, pf: PFClient) -> None:
        trace_id, span_id, line_run_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        span = mock_span(trace_id=trace_id, span_id=span_id, parent_id=None, line_run_id=line_run_id)
        span.events[0]["attributes"]["payload"] = json.dumps(dict(input1=float("nan"), input2=float("inf")))
        span.events[1]["attributes"]["payload"] = json.dumps(dict(output1=float("nan"), output2=float("-inf")))
        span._persist()
        line_run = pf.traces.get_line_run(line_run_id=line_run_id)
        line_run_inputs, line_run_outputs = line_run.inputs, line_run.outputs
        assert isinstance(line_run_inputs["input1"], str) and line_run_inputs["input1"] == "NaN"
        assert isinstance(line_run_inputs["input2"], str) and line_run_inputs["input2"] == "Infinity"
        assert isinstance(line_run_outputs["output1"], str) and line_run_outputs["output1"] == "NaN"
        assert isinstance(line_run_outputs["output2"], str) and line_run_outputs["output2"] == "-Infinity"

    def test_delete_traces_three_tables(self, pf: PFClient) -> None:
        # trace operation does not expose API for events and spans
        # so directly use ORM class to list and assert events and spans existence and deletion
        from promptflow._sdk._orm.trace import Event as ORMEvent
        from promptflow._sdk._orm.trace import LineRun as ORMLineRun
        from promptflow._sdk._orm.trace import Span as ORMSpan

        mock_run = str(uuid.uuid4())
        mock_span = mock_span_for_delete_tests(run=mock_run)
        # assert events, span and line_run are persisted
        assert len(ORMEvent.list(trace_id=mock_span.trace_id, span_id=mock_span.span_id)) == 2
        assert len(ORMSpan.list(trace_ids=[mock_span.trace_id])) == 1
        assert len(ORMLineRun.list(runs=[mock_run])) == 1
        # delete traces and assert all traces are deleted
        pf.traces.delete(run=mock_run)
        assert len(ORMEvent.list(trace_id=mock_span.trace_id, span_id=mock_span.span_id)) == 0
        assert len(ORMSpan.list(trace_ids=[mock_span.trace_id])) == 0
        assert len(ORMLineRun.list(runs=[mock_run])) == 0

    def test_delete_traces_with_run(self, pf: PFClient) -> None:
        mock_run = str(uuid.uuid4())
        mock_span_for_delete_tests(run=mock_run)
        assert len(pf.traces.list_line_runs(runs=[mock_run])) == 1
        pf.traces.delete(run=mock_run)
        assert len(pf.traces.list_line_runs(runs=[mock_run])) == 0

    def test_delete_traces_with_collection(self, pf: PFClient) -> None:
        mock_collection = str(uuid.uuid4())
        mock_span_for_delete_tests(collection=mock_collection)
        assert len(pf.traces.list_line_runs(collection=mock_collection)) == 1
        pf.traces.delete(collection=mock_collection)
        assert len(pf.traces.list_line_runs(collection=mock_collection)) == 0

    def test_delete_traces_with_collection_and_started_before(self, pf: PFClient) -> None:
        # mock some traces that start 2 days before, and delete those start 1 days before
        mock_start_time = datetime.datetime.now() - datetime.timedelta(days=2)
        collection1, collection2 = str(uuid.uuid4()), str(uuid.uuid4())
        mock_span_for_delete_tests(collection=collection1, start_time=mock_start_time)
        mock_span_for_delete_tests(collection=collection2, start_time=mock_start_time)
        assert (
            len(pf.traces.list_line_runs(collection=collection1)) == 1
            and len(pf.traces.list_line_runs(collection=collection2)) == 1
        )
        delete_query_time = datetime.datetime.now() - datetime.timedelta(days=1)
        pf.traces.delete(collection=collection1, started_before=delete_query_time.isoformat())
        # only collection1 traces are deleted
        assert (
            len(pf.traces.list_line_runs(collection=collection1)) == 0
            and len(pf.traces.list_line_runs(collection=collection2)) == 1
        )
        pf.traces.delete(collection=collection2, started_before=delete_query_time.isoformat())
        assert len(pf.traces.list_line_runs(collection=collection2)) == 0

    def test_delete_traces_dry_run(self, pf: PFClient) -> None:
        mock_run = str(uuid.uuid4())
        mock_span_for_delete_tests(run=mock_run)
        num_traces = pf.traces.delete(run=mock_run, dry_run=True)
        assert num_traces == 1

    def test_basic_search_line_runs(self, pf: PFClient) -> None:
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        line_run_id = str(uuid.uuid4())
        span = mock_span(trace_id=trace_id, span_id=span_id, parent_id=None, line_run_id=line_run_id)
        name = str(uuid.uuid4())
        span.name = name
        span._persist()
        expr = f"name == '{name}'"
        line_runs = pf.traces._search_line_runs(expression=expr)
        assert len(line_runs) == 1

    @pytest.mark.skipif(
        platform.system() == "Windows" and sys.version_info < (3, 9),
        reason="Python 3.9+ is required on Windows to support json_extract",
    )
    def test_search_line_runs_with_tokens(self, pf: PFClient) -> None:
        num_line_runs = 5
        trace_ids = list()
        name = str(uuid.uuid4())
        for _ in range(num_line_runs):
            trace_id = str(uuid.uuid4())
            span_id = str(uuid.uuid4())
            line_run_id = str(uuid.uuid4())
            span = mock_span(trace_id=trace_id, span_id=span_id, parent_id=None, line_run_id=line_run_id)
            span.name = name
            span.attributes.update({"__computed__.cumulative_token_count.total": "42"})
            span._persist()
            trace_ids.append(trace_id)
        expr = f"name == '{name}' and total < 100"
        line_runs = pf.traces._search_line_runs(expression=expr)
        assert len(line_runs) == num_line_runs
        # assert these line runs are exactly the ones we just persisted
        line_run_trace_ids = {line_run.trace_id for line_run in line_runs}
        assert len(set(trace_ids) & line_run_trace_ids) == num_line_runs

    def test_list_collection(self, pf: PFClient) -> None:
        collection = str(uuid.uuid4())
        span = mock_span(
            trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4()), parent_id=None, line_run_id=str(uuid.uuid4())
        )
        # make span start time a week later, so that it can be the latest collection
        span.start_time = datetime.datetime.now() + datetime.timedelta(days=7)
        span.start_time = datetime.datetime.now() + datetime.timedelta(days=8)
        span.resource[SpanResourceFieldName.ATTRIBUTES][SpanResourceAttributesFieldName.COLLECTION] = collection
        span._persist()
        collections = pf.traces._list_collections(limit=1)
        assert len(collections) == 1 and collections[0].name == collection

    def test_list_collection_with_time_priority(self, pf: PFClient) -> None:
        collection1, collection2 = str(uuid.uuid4()), str(uuid.uuid4())
        for collection in (collection1, collection2):
            span = mock_span(
                trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4()), parent_id=None, line_run_id=str(uuid.uuid4())
            )
            # make span start time a week later, so that it can be the latest collection
            span.start_time = datetime.datetime.now() + datetime.timedelta(days=7)
            span.start_time = datetime.datetime.now() + datetime.timedelta(days=8)
            span.resource[SpanResourceFieldName.ATTRIBUTES][SpanResourceAttributesFieldName.COLLECTION] = collection
            span._persist()
            # sleep 1 second to ensure the second span is later than the first
            time.sleep(1)
        collections = pf.traces._list_collections(limit=1)
        assert len(collections) == 1 and collections[0].name == collection2
        collections = pf.traces._list_collections(limit=2)
        assert len(collections) == 2 and collections[1].name == collection1


@pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
@pytest.mark.e2etest
@pytest.mark.sdk_test
class TestTraceWithDevKit:
    def test_flow_test_trace_enabled(self, pf: PFClient) -> None:
        import promptflow._sdk._orchestrator.test_submitter

        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            with patch.object(promptflow._sdk._orchestrator.test_submitter, "start_trace") as mock_start_trace:
                inputs = {"url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g", "answer": "Channel", "evidence": "Url"}
                pf.test(flow=Path(f"{FLOWS_DIR}/web_classification").absolute(), inputs=inputs)
                assert mock_start_trace.call_count == 1

    def test_flow_test_single_node_trace_not_enabled(self, pf: PFClient) -> None:
        import promptflow._sdk._orchestrator.test_submitter

        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            with patch.object(promptflow._sdk._orchestrator.test_submitter, "start_trace") as mock_start_trace:
                pf.test(
                    flow=Path(f"{FLOWS_DIR}/web_classification").absolute(),
                    inputs={"fetch_url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g"},
                    node="fetch_text_content_from_url",
                )
                assert mock_start_trace.call_count == 0


@pytest.mark.usefixtures("otlp_collector", "recording_injection", "setup_local_connection", "use_secrets_config_file")
@pytest.mark.e2etest
@pytest.mark.sdk_test
class TestTraceLifeCycle:
    """End-to-end tests that cover the trace lifecycle."""

    def _clear_module_cache(self, module_name) -> None:
        # referenced from test_flow_test.py::clear_module_cache
        try:
            del sys.modules[module_name]
        except Exception:  # pylint: disable=broad-except
            pass

    def _pf_test_and_assert(
        self,
        pf: PFClient,
        flow_path: Path,
        inputs: typing.Dict[str, str],
        collection: str,
    ) -> None:
        pf.test(flow=flow_path, inputs=inputs)
        line_runs = pf.traces.list_line_runs(collection=collection)
        assert len(line_runs) == 1

    def test_flow_test_dag_flow(self, pf: PFClient, collection: str) -> None:
        flow_path = Path(f"{FLOWS_DIR}/web_classification").absolute()
        inputs = {"url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g", "answer": "Channel", "evidence": "Url"}
        self._pf_test_and_assert(pf, flow_path, inputs, collection)

    def test_flow_test_flex_flow(self, pf: PFClient, collection: str) -> None:
        self._clear_module_cache("entry")
        flow_path = Path(f"{FLEX_FLOWS_DIR}/simple_with_yaml").absolute()
        inputs = {"input_val": "val1"}
        self._pf_test_and_assert(pf, flow_path, inputs, collection)

    def test_flow_test_prompty(self, pf: PFClient, collection: str) -> None:
        flow_path = Path(f"{PROMPTY_DIR}/prompty_example.prompty").absolute()
        inputs = {"question": "what is the result of 1+1?"}
        self._pf_test_and_assert(pf, flow_path, inputs, collection)

    def _pf_run_and_assert(
        self,
        pf: PFClient,
        flow_path: Path,
        data_path: Path,
        expected_number_lines: int,
    ):
        run = pf.run(flow=flow_path, data=data_path)
        line_runs = pf.traces.list_line_runs(runs=run.name)
        assert len(line_runs) == expected_number_lines

    def test_batch_run_dag_flow(self, pf: PFClient) -> None:
        flow_path = Path(f"{FLOWS_DIR}/web_classification").absolute()
        data_path = Path(f"{DATA_DIR}/webClassification3.jsonl").absolute()
        self._pf_run_and_assert(pf, flow_path, data_path, expected_number_lines=3)

    def test_batch_run_flex_flow(self, pf: PFClient) -> None:
        flow_path = Path(f"{FLEX_FLOWS_DIR}/simple_with_yaml").absolute()
        data_path = Path(f"{DATA_DIR}/simple_eager_flow_data.jsonl").absolute()
        self._pf_run_and_assert(pf, flow_path, data_path, expected_number_lines=1)

    def test_batch_run_prompty(self, pf: PFClient) -> None:
        flow_path = Path(f"{PROMPTY_DIR}/prompty_example.prompty").absolute()
        data_path = Path(f"{DATA_DIR}/prompty_inputs.jsonl").absolute()
        self._pf_run_and_assert(pf, flow_path, data_path, expected_number_lines=3)
