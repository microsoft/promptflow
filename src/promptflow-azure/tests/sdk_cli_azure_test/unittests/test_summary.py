import datetime
from dataclasses import asdict
from unittest import mock

import pytest

from promptflow._constants import OK_LINE_RUN_STATUS, SpanAttributeFieldName, SpanStatusFieldName
from promptflow._sdk.entities._trace import Span
from promptflow.azure._storage.cosmosdb.summary import InsertEvaluationsRetriableException, Summary, SummaryLine


@pytest.mark.unittest
class TestSummary:
    FAKE_CREATED_BY = {"oid": "fake_oid"}
    FAKE_COLLECTION_ID = "fake_collection_id"
    FAKE_LOGGER = mock.Mock()

    @pytest.fixture(autouse=True)
    def setup_data(self):
        test_span = Span(
            trace_id="test_trace_id",
            span_id="0987654321",
            name="test_span",
            context={"trace_id": "test_trace_id", "span_id": "0987654321"},
            kind="client",
            start_time=datetime.datetime.fromisoformat("2022-01-01T00:00:00"),
            end_time=datetime.datetime.fromisoformat("2022-01-01T00:01:00"),
            status={"status_code": OK_LINE_RUN_STATUS},
            attributes={"key1": "value1", "key2": "value2"},
            resource={"type": "resource_type", "name": "resource_name", "collection": "test_session_id"},
            parent_id="9876543210",
            events=[{"name": "event1", "time": "2022-01-01T00:00:30"}],
            links=[{"trace_id": "0987654321", "span_id": "1234567890"}],
        )
        test_span.events = [
            {
                "name": "promptflow.function.inputs",
                "attributes": {"payload": '{"input_key": "input_value"}'},
            },
            {
                "name": "promptflow.function.output",
                "attributes": {"payload": '{"output_key": "output_value"}'},
            },
        ]
        self.summary = Summary(test_span, self.FAKE_COLLECTION_ID, self.FAKE_CREATED_BY, self.FAKE_LOGGER)
        # Just for assert purpose
        self.summary.item = SummaryLine(
            id="test_trace_id",
            partition_key=self.FAKE_COLLECTION_ID,
            collection_id=self.FAKE_COLLECTION_ID,
            session_id="test_session_id",
            line_run_id="line_run_id",
            trace_id=self.summary.span.trace_id,
            root_span_id=self.summary.span.span_id,
        )

    def test_aggregate_node_span_does_not_persist(self):
        mock_client = mock.Mock()
        self.summary.span.attributes.update({SpanAttributeFieldName.IS_AGGREGATION: True})

        with mock.patch.multiple(
            self.summary,
            _persist_running_item=mock.DEFAULT,
            _persist_line_run=mock.DEFAULT,
            _insert_evaluation_with_retry=mock.DEFAULT,
        ) as values:
            self.summary.persist(mock_client)
            values["_persist_running_item"].assert_not_called()
            values["_persist_line_run"].assert_not_called()
            values["_insert_evaluation_with_retry"].assert_not_called()

    def test_non_root_span_persist_running_node(self):
        mock_client = mock.Mock()
        self.summary.span.parent_id = "parent_span_id"

        with mock.patch.multiple(
            self.summary,
            _persist_running_item=mock.DEFAULT,
            _persist_line_run=mock.DEFAULT,
            _insert_evaluation_with_retry=mock.DEFAULT,
        ) as values:
            self.summary.persist(mock_client)
            values["_persist_running_item"].assert_called_once()
            values["_persist_line_run"].assert_not_called()
            values["_insert_evaluation_with_retry"].assert_not_called()

    def test_root_span_persist_main_line(self):
        mock_client = mock.Mock()
        self.summary.span.parent_id = None
        attributes = self.summary.span.attributes
        attributes.pop(SpanAttributeFieldName.LINE_RUN_ID, None)
        attributes.pop(SpanAttributeFieldName.BATCH_RUN_ID, None)
        with mock.patch.multiple(
            self.summary,
            _persist_running_item=mock.DEFAULT,
            _persist_line_run=mock.DEFAULT,
            _insert_evaluation_with_retry=mock.DEFAULT,
        ) as values:
            self.summary.persist(mock_client)
            values["_persist_running_item"].assert_not_called()
            values["_persist_line_run"].assert_called_once()
            values["_insert_evaluation_with_retry"].assert_not_called()

    def test_root_eval_span_persist_eval(self):
        mock_client = mock.Mock()
        self.summary.span.parent_id = None
        self.summary.span.attributes[SpanAttributeFieldName.LINE_RUN_ID] = "line_run_id"
        self.summary.span.attributes[SpanAttributeFieldName.REFERENCED_LINE_RUN_ID] = "main_line_run_id"
        with mock.patch.multiple(
            self.summary,
            _persist_running_item=mock.DEFAULT,
            _persist_line_run=mock.DEFAULT,
            _insert_evaluation_with_retry=mock.DEFAULT,
        ) as values:
            self.summary.persist(mock_client)
            values["_persist_running_item"].assert_not_called()
            values["_persist_line_run"].assert_called_once()
            values["_insert_evaluation_with_retry"].assert_called_once()

    @pytest.mark.parametrize(
        "run_id_dict, expected_line_run_id, expected_batch_run_id, expected_line_number",
        [
            [{}, None, None, None],
            [
                {
                    SpanAttributeFieldName.LINE_NUMBER: "1",
                },
                None,
                None,
                None,
            ],
            [{SpanAttributeFieldName.BATCH_RUN_ID: "batch_run_id"}, None, None, None],
            [
                {
                    SpanAttributeFieldName.BATCH_RUN_ID: "batch_run_id",
                    SpanAttributeFieldName.LINE_NUMBER: "1",
                },
                None,
                "batch_run_id",
                "1",
            ],
            [{SpanAttributeFieldName.LINE_RUN_ID: "line_run_id"}, "line_run_id", None, None],
        ],
    )
    def test_prepare_db_item(self, run_id_dict, expected_line_run_id, expected_batch_run_id, expected_line_number):
        self.summary.span.start_time = datetime.datetime.fromisoformat("2022-01-01T00:00:00")
        self.summary.span.end_time = datetime.datetime.fromisoformat("2022-01-01T00:01:00")
        self.summary.span.attributes = {
            SpanAttributeFieldName.COMPLETION_TOKEN_COUNT: 10,
            SpanAttributeFieldName.PROMPT_TOKEN_COUNT: 5,
            SpanAttributeFieldName.TOTAL_TOKEN_COUNT: 15,
            SpanAttributeFieldName.SPAN_TYPE: "span_type",
        }
        self.summary.span.attributes.update(run_id_dict)

        self.summary._prepare_db_item()

        assert self.summary.item.id == self.summary.span.trace_id
        assert self.summary.item.partition_key == self.summary.collection_id
        assert self.summary.item.session_id == self.summary.session_id
        assert self.summary.item.trace_id == self.summary.span.trace_id
        assert self.summary.item.collection_id == self.summary.collection_id
        assert self.summary.item.root_span_id == self.summary.span.span_id
        assert self.summary.item.inputs == self.summary.inputs
        assert self.summary.item.outputs == self.summary.outputs
        assert self.summary.item.start_time == "2022-01-01T00:00:00"
        assert self.summary.item.end_time == "2022-01-01T00:01:00"
        assert self.summary.item.status == self.summary.span.status[SpanStatusFieldName.STATUS_CODE]
        assert self.summary.item.latency == 60.0
        assert self.summary.item.name == self.summary.span.name
        assert self.summary.item.kind == "span_type"
        assert self.summary.item.cumulative_token_count == {
            "completion": 10,
            "prompt": 5,
            "total": 15,
        }
        assert self.summary.item.created_by == self.summary.created_by
        assert self.summary.item.line_run_id == expected_line_run_id
        assert self.summary.item.batch_run_id == expected_batch_run_id
        assert self.summary.item.line_number == expected_line_number

    @pytest.mark.parametrize(
        "return_value",
        [
            [],  # No item found
            [{"id": "main_id"}],  # Not finished
        ],
    )
    def test_insert_evaluation_no_action(self, return_value):
        client = mock.Mock()
        self.summary.span.attributes = {
            SpanAttributeFieldName.REFERENCED_LINE_RUN_ID: "referenced_line_run_id",
            SpanAttributeFieldName.LINE_RUN_ID: "line_run_id",
        }

        client.query_items.return_value = []
        with pytest.raises(InsertEvaluationsRetriableException):
            self.summary._insert_evaluation(client)
        client.query_items.assert_called_once()
        client.patch_item.assert_not_called()

    def test_insert_evaluation_query_line_run(self):
        client = mock.Mock()
        self.summary.span.attributes = {
            SpanAttributeFieldName.REFERENCED_LINE_RUN_ID: "referenced_line_run_id",
            SpanAttributeFieldName.LINE_RUN_ID: "line_run_id",
        }
        client.query_items.return_value = [
            {"id": "main_id", "partition_key": "test_main_partition_key", "status": OK_LINE_RUN_STATUS}
        ]
        self.summary._insert_evaluation(client)
        client.query_items.assert_called_once_with(
            query=(
                "SELECT * FROM c WHERE "
                "c.line_run_id = @line_run_id AND c.batch_run_id = @batch_run_id AND c.line_number = @line_number"
            ),
            parameters=[
                {"name": "@line_run_id", "value": "referenced_line_run_id"},
                {"name": "@batch_run_id", "value": None},
                {"name": "@line_number", "value": None},
            ],
            enable_cross_partition_query=True,
        )
        item_dict = asdict(self.summary.item)
        del item_dict["evaluations"]

        expected_patch_operations = [
            {"op": "add", "path": f"/evaluations/{self.summary.span.name}", "value": item_dict}
        ]
        client.patch_item.assert_called_once_with(
            item="main_id",
            partition_key="test_main_partition_key",
            patch_operations=expected_patch_operations,
        )

    def test_insert_evaluation_query_batch_run(self):
        client = mock.Mock()
        self.summary.span.attributes = {
            SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID: "referenced_batch_run_id",
            SpanAttributeFieldName.BATCH_RUN_ID: "batch_run_id",
            SpanAttributeFieldName.LINE_NUMBER: 1,
        }
        client.query_items.return_value = [
            {"id": "main_id", "partition_key": "test_main_partition_key", "status": OK_LINE_RUN_STATUS}
        ]

        self.summary._insert_evaluation(client)
        client.query_items.assert_called_once_with(
            query=(
                "SELECT * FROM c WHERE "
                "c.line_run_id = @line_run_id AND c.batch_run_id = @batch_run_id AND c.line_number = @line_number"
            ),
            parameters=[
                {"name": "@line_run_id", "value": None},
                {"name": "@batch_run_id", "value": "referenced_batch_run_id"},
                {"name": "@line_number", "value": 1},
            ],
            enable_cross_partition_query=True,
        )

        item_dict = asdict(self.summary.item)
        del item_dict["evaluations"]

        expected_patch_operations = [{"op": "add", "path": "/evaluations/batch_run_id", "value": item_dict}]
        client.patch_item.assert_called_once_with(
            item="main_id",
            partition_key="test_main_partition_key",
            patch_operations=expected_patch_operations,
        )

    def test_persist_line_run(self):
        client = mock.Mock()
        self.summary._persist_line_run(client)
        client.upsert_item.assert_called_once_with(body=asdict(self.summary.item))

    def test_insert_evaluation_with_retry_success(self):
        client = mock.Mock()
        with mock.patch.object(self.summary, "_insert_evaluation") as mock_insert_evaluation:
            self.summary._insert_evaluation_with_retry(client)
            mock_insert_evaluation.assert_called_once_with(client)

    def test_insert_evaluation_with_retry_exception(self):
        client = mock.Mock()
        with mock.patch.object(self.summary, "_insert_evaluation") as mock_insert_evaluation:
            mock_insert_evaluation.side_effect = InsertEvaluationsRetriableException()
            with mock.patch("time.sleep") as mock_sleep:
                self.summary._insert_evaluation_with_retry(client)
                mock_insert_evaluation.assert_called_with(client)
                assert mock_insert_evaluation.call_count == 3
                assert mock_sleep.call_count == 2

    def test_insert_evaluation_with_non_retry_exception(self):
        client = mock.Mock()
        with mock.patch.object(self.summary, "_insert_evaluation") as mock_insert_evaluation:
            mock_insert_evaluation.side_effect = Exception()
            with pytest.raises(Exception):
                self.summary._insert_evaluation_with_retry(client)
            assert mock_insert_evaluation.call_count == 1

    def test_persist_running_item_create_item(self):
        client = mock.Mock()
        with mock.patch("promptflow.azure._storage.cosmosdb.summary.safe_create_cosmosdb_item") as mock_safe_write:
            self.summary._persist_running_item(client)
            mock_safe_write.assert_called_once()

    @pytest.mark.parametrize(
        "content, expected_result",
        [
            [
                {
                    "short_text": "Hello promptflow",
                    "numbers_list": [1, 2, 3, 4, 5],
                    "nested_dict": {"nested_key": "Lorem ipsum dolor sit amet, consectetur adipiscing elit."},
                    "integer_value": 123,
                    "float_value": 3.14,
                    "boolean_value": True,
                },
                {
                    "short_text": "Hello promptflow",
                    "numbers_list": "[...]",
                    "nested_dict": "{...}",
                    "integer_value": 123,
                    "float_value": 3.14,
                    "boolean_value": True,
                },
            ],
            ["a" * 600, "a" * 500],
            ["Hello promptflow", "Hello promptflow"],
            [[1, 2, 3, 4, 5], "[...]"],
            [{}, {}],
            [123, 123],
            [3.14, 3.14],
            [True, True],
            [None, None],
        ],
    )
    def test_truncate_and_replace_content(self, content, expected_result):

        truncated_content = self.summary._truncate_and_replace_content(content)

        assert truncated_content == expected_result

    @pytest.mark.parametrize(
        "events, expected_inputs, expected_outputs",
        [
            [[], None, None],
            [
                [
                    {
                        "name": "promptflow.function.inputs",
                        "attributes": {},  # No payload will not take effect
                    },
                    {
                        "name": "promptflow.function.output",
                        "attributes": {},  # No payload will not take effect
                    },
                    {
                        "name": "wrong name should not take effect",
                        "attributes": {"payload": '"wrong name should not take effect"'},
                    },
                    {
                        "name": "promptflow.function.inputs",
                        "attributes": {"payload": '"show first input"'},
                    },
                    {
                        "name": "promptflow.function.inputs",
                        "attributes": {"payload": '"second input"'},
                    },
                    {
                        "name": "promptflow.function.output",
                        "attributes": {"payload": '"show first output"'},
                    },
                    {
                        "name": "promptflow.function.output",
                        "attributes": {"payload": '"second  output"'},
                    },
                ],
                "show first input",
                "show first output",
            ],
        ],
    )
    def test_parse_inputs_outputs(self, events, expected_inputs, expected_outputs):
        self.summary.span.events = events
        self.summary._parse_inputs_outputs_from_events()
        assert self.summary.inputs == expected_inputs
        assert self.summary.outputs == expected_outputs
