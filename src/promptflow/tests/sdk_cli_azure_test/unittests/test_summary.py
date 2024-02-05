from dataclasses import asdict
from unittest import mock

import pytest

from promptflow._constants import SpanAttributeFieldName, SpanFieldName
from promptflow._sdk.entities._trace import Span
from promptflow.azure._storage.cosmosdb.summary import LineEvaluation, Summary, SummaryLine


class TestSummary:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        test_span = Span(
            name="test_span",
            context={"trace_id": "1234567890", "span_id": "0987654321"},
            kind="client",
            start_time="2022-01-01T00:00:00Z",
            end_time="2022-01-01T00:01:00Z",
            status="OK",
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
        self.summary = Summary(test_span)

    def test_persist_root_non_eval_span(self):
        self.summary.span.parent_span_id = None
        with mock.patch("promptflow.azure._storage.cosmosdb.summary.get_client_with_workspace_info") as mock_get_client:
            mock_get_client.return_value = "client"
            with mock.patch.object(self.summary, "_persist_line_run") as mock_persist_line_run:
                with mock.patch.object(self.summary, "_insert_evaluation") as mock_insert_evaluation:
                    self.summary.persist()
                    mock_persist_line_run.assert_called_once()
                    mock_insert_evaluation.assert_not_called()

    def test_persist_root_eval_span(self):
        self.summary.span.parent_span_id = None
        self.summary.span._content = {
            "attributes": {
                # Set referenced line run id to test the evaluation insertion
                SpanAttributeFieldName.REFERENCED_LINE_RUN_ID: "line_run_id"
            }
        }
        with mock.patch("promptflow.azure._storage.cosmosdb.summary.get_client_with_workspace_info") as mock_get_client:
            mock_get_client.return_value = "client"
            with mock.patch.object(self.summary, "_persist_line_run") as mock_persist_line_run:
                with mock.patch.object(self.summary, "_insert_evaluation") as mock_insert_evaluation:
                    self.summary.persist()
                    mock_persist_line_run.assert_called_once()
                    mock_insert_evaluation.assert_called_once()

    def test_persist_non_root_span(self):
        self.summary.span.parent_span_id = "parent_span_id"
        with mock.patch("promptflow.azure._storage.cosmosdb.summary.get_client_with_workspace_info") as mock_get_client:
            self.summary.persist()
            mock_get_client.assert_not_called()

    def test__insert_evaluation(self):
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
        )
        expected_patch_operations = [
            {"op": "add", "path": f"/evaluations/{self.summary.span.name}", "value": asdict(expected_item)}
        ]

        with mock.patch.object(client, "patch_item") as mock_patch_item:
            self.summary._insert_evaluation(client)
            mock_patch_item.assert_called_once_with(
                item="referenced_line_run_id",
                partition_key="test_session_id",
                patch_operations=expected_patch_operations,
            )

    def test__persist_line_run(self):
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
            cumulative_token_count={
                "completion": 10,
                "prompt": 5,
                "total": 15,
            },
        )

        with mock.patch.object(client, "create_item") as mock_create_item:
            self.summary._persist_line_run(client)
            mock_create_item.assert_called_once_with(body=asdict(expected_item))
