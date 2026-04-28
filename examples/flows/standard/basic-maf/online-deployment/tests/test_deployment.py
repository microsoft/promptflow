"""Tests for the basic-maf online deployment files.

Validates scoring script structure, YAML correctness, conda packages,
and deploy script configuration.
"""

from pathlib import Path

import pytest
import yaml


DEPLOY_DIR = Path(__file__).resolve().parent.parent


class TestScoreScript:
    def test_exists(self):
        assert (DEPLOY_DIR / "score.py").exists()

    def test_has_init(self):
        content = (DEPLOY_DIR / "score.py").read_text()
        assert "def init():" in content

    def test_has_run(self):
        content = (DEPLOY_DIR / "score.py").read_text()
        assert "def run(raw_data):" in content

    def test_imports_workflow(self):
        content = (DEPLOY_DIR / "score.py").read_text()
        assert "from workflow import create_workflow" in content

    def test_handles_text_input(self):
        """Scoring script should parse 'text' field matching workflow.run() input."""
        content = (DEPLOY_DIR / "score.py").read_text()
        assert '"text"' in content

    def test_handles_agent_response(self):
        content = (DEPLOY_DIR / "score.py").read_text()
        assert 'hasattr(output, "text")' in content


class TestCondaYml:
    def test_valid_yaml(self):
        with open(DEPLOY_DIR / "conda.yml") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)

    def test_has_python_311(self):
        with open(DEPLOY_DIR / "conda.yml") as f:
            data = yaml.safe_load(f)
        assert "python=3.11" in data["dependencies"]

    def test_has_agent_framework_openai(self):
        with open(DEPLOY_DIR / "conda.yml") as f:
            data = yaml.safe_load(f)
        pip_deps = None
        for dep in data["dependencies"]:
            if isinstance(dep, dict) and "pip" in dep:
                pip_deps = dep["pip"]
        assert pip_deps is not None
        assert "agent-framework" in pip_deps
        assert "agent-framework-openai" in pip_deps

    def test_has_inference_server(self):
        with open(DEPLOY_DIR / "conda.yml") as f:
            data = yaml.safe_load(f)
        pip_deps = [d for d in data["dependencies"] if isinstance(d, dict) and "pip" in d][0]["pip"]
        assert "azureml-inference-server-http" in pip_deps

    def test_no_foundry_packages(self):
        """This workflow uses OpenAI, not Foundry."""
        with open(DEPLOY_DIR / "conda.yml") as f:
            data = yaml.safe_load(f)
        pip_deps = [d for d in data["dependencies"] if isinstance(d, dict) and "pip" in d][0]["pip"]
        for pkg in pip_deps:
            assert "foundry" not in pkg.lower()
            assert "ai-search" not in pkg.lower()


class TestEndpointYml:
    def test_valid_yaml(self):
        with open(DEPLOY_DIR / "endpoint.yml") as f:
            data = yaml.safe_load(f)
        assert data["name"] == "basic-maf-endpoint"
        assert data["auth_mode"] == "key"

    def test_has_schema(self):
        with open(DEPLOY_DIR / "endpoint.yml") as f:
            data = yaml.safe_load(f)
        assert "$schema" in data


class TestDeploymentYml:
    def test_has_schema_line(self):
        content = (DEPLOY_DIR / "deployment.yml").read_text()
        assert "$schema:" in content

    def test_has_openai_env_vars(self):
        content = (DEPLOY_DIR / "deployment.yml").read_text()
        assert "${AZURE_OPENAI_ENDPOINT}" in content
        assert "${AZURE_OPENAI_DEPLOYMENT}" in content
        assert "${AZURE_OPENAI_API_KEY}" in content

    def test_no_foundry_env_vars(self):
        content = (DEPLOY_DIR / "deployment.yml").read_text()
        assert "FOUNDRY_PROJECT_ENDPOINT" not in content
        assert "FOUNDRY_MODEL" not in content

    def test_request_timeout(self):
        content = (DEPLOY_DIR / "deployment.yml").read_text()
        assert "request_timeout_ms: 60000" in content

    def test_uses_conda_file(self):
        content = (DEPLOY_DIR / "deployment.yml").read_text()
        assert "conda_file:" in content
        assert "pip_requirements:" not in content

    def test_endpoint_name_matches(self):
        content = (DEPLOY_DIR / "deployment.yml").read_text()
        assert "endpoint_name: basic-maf-endpoint" in content


class TestDeployScript:
    def test_exists(self):
        assert (DEPLOY_DIR / "deploy.sh").exists()

    def test_uses_restricted_envsubst(self):
        content = (DEPLOY_DIR / "deploy.sh").read_text()
        assert "SUBST_VARS=" in content
        assert 'envsubst "$SUBST_VARS"' in content

    def test_requires_openai_vars(self):
        content = (DEPLOY_DIR / "deploy.sh").read_text()
        assert "AZURE_OPENAI_ENDPOINT" in content
        assert "AZURE_OPENAI_DEPLOYMENT" in content
        assert "AZURE_OPENAI_API_KEY" in content

    def test_smoke_test_uses_text_field(self):
        content = (DEPLOY_DIR / "deploy.sh").read_text()
        assert '"text"' in content
