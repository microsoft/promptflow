import pytest
from pathlib import Path

from promptflow.exceptions import UserErrorException
from promptflow.core.tracer import Tracer
from promptflow.connections import OpenAIConnection
from promptflow.tools.openai import completion


PROMOTFLOW_ROOT = Path(__file__) / "../../../../"


@pytest.mark.unittest
class TestTracerErrors:
    def test_traces_failed(self):
        run_id = "dummy_run_id"
        prompt = "This is a test"
        api_key = "DummyKey"
        organization = "TestOrg"
        conn = OpenAIConnection(api_key=api_key, organization=organization)
        Tracer.start_tracing(run_id)

        with pytest.raises(UserErrorException) as ex:
            completion(conn, prompt=prompt)

        result = Tracer.end_tracing(raise_ex=True)
        assert result is not None
        assert len(result) == 1
        item = result[0]
        assert item["error"]["type"] in ex.value.message
        assert item["output"] is None
        self.assert_openai_completion_trace(item, prompt, conn)

    def assert_openai_completion_trace(self, item, prompt, conn):
        assert isinstance(item["inputs"], dict)
        assert prompt == item["inputs"]["prompt"]
        assert conn.organization == item["inputs"]["organization"]
        assert isinstance(item["start_time"], float)
        assert isinstance(item["end_time"], float)
        assert item["start_time"] < item["end_time"]
        assert "LLM" == item["type"]
        assert "openai.api_resources.completion.Completion.create" == item["name"]
