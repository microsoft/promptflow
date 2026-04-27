"""
Live smoke tests for the basic-maf managed online endpoint.

Prerequisites
-------------
- az login (authenticated Azure CLI session)
- The endpoint 'basic-maf-endpoint' is deployed and healthy.

Run
---
    python -m pytest online-deployment/tests/test_endpoint_live.py -v
"""

import json
import subprocess
import tempfile
import os
import pytest

SUBSCRIPTION = "33a557c9-fcf9-4606-aa30-250e4bb8c146"
RESOURCE_GROUP = "lusu-pf"
WORKSPACE = "lusu-pf"
ENDPOINT_NAME = "basic-maf-endpoint"


def _invoke_endpoint(payload: dict) -> dict:
    """Call the endpoint via `az ml online-endpoint invoke` and return parsed JSON."""
    # Write payload to a temp file (cross-platform; /dev/stdin doesn't exist on Windows).
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp:
        json.dump(payload, tmp)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                "az", "ml", "online-endpoint", "invoke",
                "--subscription", SUBSCRIPTION,
                "--resource-group", RESOURCE_GROUP,
                "--workspace-name", WORKSPACE,
                "--name", ENDPOINT_NAME,
                "--request-file", tmp_path,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            shell=True,
        )
    finally:
        os.unlink(tmp_path)

    assert result.returncode == 0, f"Endpoint invocation failed:\n{result.stderr}"

    # The CLI wraps the JSON response in an extra string layer.
    raw = result.stdout.strip()
    body = json.loads(raw)
    if isinstance(body, str):
        body = json.loads(body)
    return body


class TestEndpointLive:
    """Live tests against the deployed endpoint."""

    def test_hello_world(self):
        """Basic request returns a non-empty answer."""
        resp = _invoke_endpoint({"text": "Hello World!"})
        assert "answer" in resp, f"Response missing 'answer' key: {resp}"
        assert len(resp["answer"]) > 0, "Answer is empty"

    def test_answer_is_string(self):
        """The answer field should be a string."""
        resp = _invoke_endpoint({"text": "Write a hello world in Python"})
        assert isinstance(resp["answer"], str)

    def test_answer_contains_code(self):
        """Asking for code should return something resembling code."""
        resp = _invoke_endpoint({"text": "Write a hello world in Python"})
        answer = resp["answer"].lower()
        assert "print" in answer or "hello" in answer, (
            f"Expected code-like output, got: {resp['answer'][:200]}"
        )

    def test_empty_text_returns_error(self):
        """An empty text field should produce an error (non-zero exit or error body)."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp:
            json.dump({"text": ""}, tmp)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                [
                    "az", "ml", "online-endpoint", "invoke",
                    "--subscription", SUBSCRIPTION,
                    "--resource-group", RESOURCE_GROUP,
                    "--workspace-name", WORKSPACE,
                    "--name", ENDPOINT_NAME,
                    "--request-file", tmp_path,
                ],
                capture_output=True,
                text=True,
                timeout=120,
                shell=True,
            )
        finally:
            os.unlink(tmp_path)

        # The scoring script raises ValueError for empty text,
        # which AML surfaces as an HTTP error / non-zero exit.
        assert result.returncode != 0 or "error" in result.stdout.lower()
