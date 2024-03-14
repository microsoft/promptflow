from dataclasses import asdict
from unittest import mock

import pytest
from flask import Flask

from promptflow._constants import SpanAttributeFieldName, SpanFieldName
from promptflow._sdk.entities._trace import Span
from promptflow.azure._storage.cosmosdb.summary import LineEvaluation, Summary, SummaryLine


@pytest.mark.unittest
class TestSummary:
    FAKE_CREATED_BY = {"oid": "fake_oid"}
    FAKE_LOGGER = mock.Mock()

    @pytest.fixture(autouse=True)
    def setup_data(self):
        test_span = Span(
            name="test_span",
            context={"trace_id": "test_trace_id", "span_id": "0987654321"},
            kind="client",
            start_time="2022-01-01T00:00:00Z",
            end_time="2022-01-01T00:01:00Z",
            status={"status_code": "OK"},
            attributes={"key1": "value1", "key2": "value2"},
            resource={"type": "resource_type", "name": "resource_name"},
            span_type="custom",
            session_id="test_session_id",
            parent_span_id="9876543210",
            events=[{"name": "event1", "time": "2022-01-01T00:00:30Z"}],
            links=[{"trace_id": "0987654321", "span_id": "1234567890"}],
            path="/path/to/span",
            run="test_run",
            experiment="test_experiment",
        )
        self.summary = Summary(test_span, self.FAKE_CREATED_BY, self.FAKE_LOGGER)
        app = Flask(__name__)
        with app.app_context():
            yield

    def test_non_root_span_does_not_persist(self):
        with mock.patch.object(self.summary, "_persist_line_run") as mock_persist_line_run, mock.patch.object(
            self.summary, "_insert_evaluation"
        ) as mock_insert_evaluation:
            mock_client = mock.Mock()
            self.summary.span.parent_span_id = "parent_span_id"
            self.summary.persist(mock_client)
            mock_persist_line_run.assert_not_called()
            mock_insert_evaluation.assert_not_called()

    def test_aggregate_run_does_not_persist(self):
        with mock.patch.object(self.summary, "_persist_line_run") as mock_persist_line_run, mock.patch.object(
            self.summary, "_insert_evaluation"
        ) as mock_insert_evaluation:
            mock_client = mock.Mock()
            self.summary.span.parent_span_id = None
            attributes = self.summary.span._content[SpanFieldName.ATTRIBUTES]
            attributes.pop(SpanAttributeFieldName.LINE_RUN_ID, None)
            attributes.pop(SpanAttributeFieldName.BATCH_RUN_ID, None)
            self.summary.persist(mock_client)
            mock_persist_line_run.assert_called_once()
            mock_insert_evaluation.assert_not_called()

    def test_non_evaluation_span_persists_as_main_run(self):
        with mock.patch.object(self.summary, "_persist_line_run") as mock_persist_line_run, mock.patch.object(
            self.summary, "_insert_evaluation"
        ) as mock_insert_evaluation:
            mock_client = mock.Mock()
            self.summary.span.parent_span_id = None
            self.summary.span._content[SpanFieldName.ATTRIBUTES][SpanAttributeFieldName.LINE_RUN_ID] = "line_run_id"
            self.summary.persist(mock_client)
            mock_persist_line_run.assert_called_once()
            mock_insert_evaluation.assert_not_called()

    def test_non_evaluation_span_persists_with_referenced_line_run_id(self):
        with mock.patch.object(self.summary, "_persist_line_run") as mock_persist_line_run, mock.patch.object(
            self.summary, "_insert_evaluation"
        ) as mock_insert_evaluation:
            mock_client = mock.Mock()
            self.summary.span.parent_span_id = None
            self.summary.span._content[SpanFieldName.ATTRIBUTES][SpanAttributeFieldName.LINE_RUN_ID] = "line_run_id"
            self.summary.span._content[SpanFieldName.ATTRIBUTES][
                SpanAttributeFieldName.REFERENCED_LINE_RUN_ID
            ] = "main_line_run_id"
            self.summary.persist(mock_client)
            mock_persist_line_run.assert_called_once()
            mock_insert_evaluation.assert_called_once()

    def test_insert_evaluation_line_run_not_exist(self):
        client = mock.Mock()
        self.summary.span._content = {
            SpanFieldName.ATTRIBUTES: {
                SpanAttributeFieldName.REFERENCED_LINE_RUN_ID: "referenced_line_run_id",
                SpanAttributeFieldName.LINE_RUN_ID: "line_run_id",
                SpanAttributeFieldName.OUTPUT: '{"output_key": "output_value"}',
            }
        }

        client.query_items.return_value = []
        self.summary._insert_evaluation(client)
        client.query_items.assert_called_once()
        client.patch_item.assert_not_called()

    def test_insert_evaluation_line_run_normal(self):
        client = mock.Mock()
        self.summary.span._content = {
            SpanFieldName.ATTRIBUTES: {
                SpanAttributeFieldName.REFERENCED_LINE_RUN_ID: "referenced_line_run_id",
                SpanAttributeFieldName.LINE_RUN_ID: "line_run_id",
                SpanAttributeFieldName.OUTPUT: '{"output_key": "output_value"}',
            }
        }
        expected_item = LineEvaluation(
            line_run_id="line_run_id",
            trace_id=self.summary.span.trace_id,
            root_span_id=self.summary.span.span_id,
            outputs={"output_key": "output_value"},
            name=self.summary.span.name,
            created_by=self.FAKE_CREATED_BY,
        )
        expected_patch_operations = [
            {"op": "add", "path": f"/evaluations/{self.summary.span.name}", "value": asdict(expected_item)}
        ]

        client.query_items.return_value = [{"id": "main_id"}]
        self.summary._insert_evaluation(client)
        client.query_items.assert_called_once()
        client.patch_item.assert_called_once_with(
            item="main_id",
            partition_key="test_session_id",
            patch_operations=expected_patch_operations,
        )

    def test_insert_evaluation_batch_run_not_exist(self):
        client = mock.Mock()
        self.summary.span._content = {
            SpanFieldName.ATTRIBUTES: {
                SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID: "referenced_batch_run_id",
                SpanAttributeFieldName.BATCH_RUN_ID: "batch_run_id",
                SpanAttributeFieldName.LINE_NUMBER: "1",
                SpanAttributeFieldName.OUTPUT: '{"output_key": "output_value"}',
            }
        }

        client.query_items.return_value = []
        self.summary._insert_evaluation(client)
        client.query_items.assert_called_once()
        client.patch_item.assert_not_called()

    def test_insert_evaluation_batch_run_normal(self):
        client = mock.Mock()
        self.summary.span._content = {
            SpanFieldName.ATTRIBUTES: {
                SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID: "referenced_batch_run_id",
                SpanAttributeFieldName.BATCH_RUN_ID: "batch_run_id",
                SpanAttributeFieldName.LINE_NUMBER: "1",
                SpanAttributeFieldName.OUTPUT: '{"output_key": "output_value"}',
            }
        }
        expected_item = LineEvaluation(
            batch_run_id="batch_run_id",
            line_number="1",
            trace_id=self.summary.span.trace_id,
            root_span_id=self.summary.span.span_id,
            outputs={"output_key": "output_value"},
            name=self.summary.span.name,
            created_by=self.FAKE_CREATED_BY,
        )

        expected_patch_operations = [
            {"op": "add", "path": f"/evaluations/{self.summary.span.name}", "value": asdict(expected_item)}
        ]

        client.query_items.return_value = [{"id": "main_id"}]
        self.summary._insert_evaluation(client)
        client.query_items.assert_called_once()
        client.patch_item.assert_called_once_with(
            item="main_id",
            partition_key="test_session_id",
            patch_operations=expected_patch_operations,
        )

    def test_persist_line_run(self):
        client = mock.Mock()
        self.summary.span._content.update(
            {
                SpanFieldName.ATTRIBUTES: {
                    SpanAttributeFieldName.LINE_RUN_ID: "line_run_id",
                    SpanAttributeFieldName.INPUTS: '{"input_key": "input_value"}',
                    SpanAttributeFieldName.OUTPUT: '{"output_key": "output_value"}',
                    SpanAttributeFieldName.SPAN_TYPE: "promptflow.TraceType.Flow",
                    SpanAttributeFieldName.COMPLETION_TOKEN_COUNT: 10,
                    SpanAttributeFieldName.PROMPT_TOKEN_COUNT: 5,
                    SpanAttributeFieldName.TOTAL_TOKEN_COUNT: 15,
                },
            }
        )
        expected_item = SummaryLine(
            id="test_trace_id",
            partition_key="test_session_id",
            session_id="test_session_id",
            line_run_id="line_run_id",
            trace_id=self.summary.span.trace_id,
            root_span_id=self.summary.span.span_id,
            inputs={"input_key": "input_value"},
            outputs={"output_key": "output_value"},
            start_time="2022-01-01T00:00:00Z",
            end_time="2022-01-01T00:01:00Z",
            status="OK",
            latency=60.0,
            name=self.summary.span.name,
            kind="promptflow.TraceType.Flow",
            created_by=self.FAKE_CREATED_BY,
            cumulative_token_count={
                "completion": 10,
                "prompt": 5,
                "total": 15,
            },
        )

        with mock.patch.object(client, "create_item") as mock_create_item:
            self.summary._persist_line_run(client)
            mock_create_item.assert_called_once_with(body=asdict(expected_item))

    def test_persist_batch_run(self):
        client = mock.Mock()
        self.summary.span._content.update(
            {
                SpanFieldName.ATTRIBUTES: {
                    SpanAttributeFieldName.BATCH_RUN_ID: "batch_run_id",
                    SpanAttributeFieldName.LINE_NUMBER: "1",
                    SpanAttributeFieldName.INPUTS: '{"input_key": "input_value"}',
                    SpanAttributeFieldName.OUTPUT: '{"output_key": "output_value"}',
                    SpanAttributeFieldName.SPAN_TYPE: "promptflow.TraceType.Flow",
                    SpanAttributeFieldName.COMPLETION_TOKEN_COUNT: 10,
                    SpanAttributeFieldName.PROMPT_TOKEN_COUNT: 5,
                    SpanAttributeFieldName.TOTAL_TOKEN_COUNT: 15,
                },
            }
        )
        expected_item = SummaryLine(
            id="test_trace_id",
            partition_key="test_session_id",
            session_id="test_session_id",
            batch_run_id="batch_run_id",
            line_number="1",
            trace_id=self.summary.span.trace_id,
            root_span_id=self.summary.span.span_id,
            inputs={"input_key": "input_value"},
            outputs={"output_key": "output_value"},
            start_time="2022-01-01T00:00:00Z",
            end_time="2022-01-01T00:01:00Z",
            status="OK",
            latency=60.0,
            name=self.summary.span.name,
            created_by=self.FAKE_CREATED_BY,
            kind="promptflow.TraceType.Flow",
            cumulative_token_count={
                "completion": 10,
                "prompt": 5,
                "total": 15,
            },
        )

        with mock.patch.object(client, "create_item") as mock_create_item:
            self.summary._persist_line_run(client)
            mock_create_item.assert_called_once_with(body=asdict(expected_item))
