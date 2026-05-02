"""Tests for the MAF online endpoint skill assets.

Validates:
- score.py can be imported and has init/run functions
- YAML templates are valid YAML
- deploy.sh is syntactically valid bash
- conda.yml has required packages
"""

import importlib.util
from pathlib import Path

import yaml


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


class TestScoreScript:
    """Validate the scoring script template."""

    def _load_module(self):
        spec = importlib.util.spec_from_file_location("score", ASSETS_DIR / "score.py")
        module = importlib.util.module_from_spec(spec)
        # Don't exec — just check structure
        return spec, module

    def test_score_file_exists(self):
        assert (ASSETS_DIR / "score.py").exists()

    def test_has_init_function(self):
        content = (ASSETS_DIR / "score.py").read_text()
        assert "def init():" in content

    def test_has_run_function(self):
        content = (ASSETS_DIR / "score.py").read_text()
        assert "def run(raw_data):" in content

    def test_handles_agent_response(self):
        """score.py must extract .text from AgentResponse."""
        content = (ASSETS_DIR / "score.py").read_text()
        assert 'hasattr(output, "text")' in content

    def test_handles_empty_question(self):
        content = (ASSETS_DIR / "score.py").read_text()
        assert "must not be empty" in content


class TestCondaYml:
    """Validate the conda environment template."""

    def test_file_exists(self):
        assert (ASSETS_DIR / "conda.yml").exists()

    def test_valid_yaml(self):
        with open(ASSETS_DIR / "conda.yml") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)

    def test_has_python_311(self):
        with open(ASSETS_DIR / "conda.yml") as f:
            data = yaml.safe_load(f)
        deps = data.get("dependencies", [])
        assert "python=3.11" in deps

    def test_has_required_pip_packages(self):
        with open(ASSETS_DIR / "conda.yml") as f:
            data = yaml.safe_load(f)
        pip_deps = None
        for dep in data.get("dependencies", []):
            if isinstance(dep, dict) and "pip" in dep:
                pip_deps = dep["pip"]
                break
        assert pip_deps is not None
        assert "agent-framework" in pip_deps
        assert "azureml-inference-server-http" in pip_deps
        assert "azure-identity" in pip_deps

    def test_no_version_pins(self):
        """Verify no strict version pins that could break builds."""
        with open(ASSETS_DIR / "conda.yml") as f:
            data = yaml.safe_load(f)
        for dep in data.get("dependencies", []):
            if isinstance(dep, dict) and "pip" in dep:
                for pkg in dep["pip"]:
                    assert "==" not in pkg, f"Version pin found: {pkg}"


class TestEndpointYml:
    """Validate the endpoint YAML template."""

    def test_file_exists(self):
        assert (ASSETS_DIR / "endpoint.yml").exists()

    def test_valid_yaml(self):
        with open(ASSETS_DIR / "endpoint.yml") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)

    def test_has_schema(self):
        with open(ASSETS_DIR / "endpoint.yml") as f:
            data = yaml.safe_load(f)
        assert "$schema" in data

    def test_has_auth_mode(self):
        with open(ASSETS_DIR / "endpoint.yml") as f:
            data = yaml.safe_load(f)
        assert data.get("auth_mode") == "key"


class TestDeploymentYml:
    """Validate the deployment YAML template."""

    def test_file_exists(self):
        assert (ASSETS_DIR / "deployment.yml").exists()

    def test_has_schema_line(self):
        content = (ASSETS_DIR / "deployment.yml").read_text()
        assert "$schema:" in content

    def test_has_request_timeout(self):
        content = (ASSETS_DIR / "deployment.yml").read_text()
        assert "request_timeout_ms: 60000" in content

    def test_has_conda_file_not_pip_requirements(self):
        content = (ASSETS_DIR / "deployment.yml").read_text()
        assert "conda_file:" in content
        assert "pip_requirements:" not in content

    def test_uses_envsubst_placeholders(self):
        content = (ASSETS_DIR / "deployment.yml").read_text()
        assert "${FOUNDRY_PROJECT_ENDPOINT}" in content
        assert "${FOUNDRY_MODEL}" in content

    def test_environment_variables_section(self):
        content = (ASSETS_DIR / "deployment.yml").read_text()
        assert "environment_variables:" in content


class TestDeployScript:
    """Validate the deploy shell script."""

    def test_file_exists(self):
        assert (ASSETS_DIR / "deploy.sh").exists()

    def test_uses_restricted_envsubst(self):
        """envsubst must use restricted vars to preserve $schema."""
        content = (ASSETS_DIR / "deploy.sh").read_text()
        assert "SUBST_VARS=" in content
        assert 'envsubst "$SUBST_VARS"' in content

    def test_has_set_euo_pipefail(self):
        content = (ASSETS_DIR / "deploy.sh").read_text()
        assert "set -euo pipefail" in content

    def test_requires_mandatory_vars(self):
        content = (ASSETS_DIR / "deploy.sh").read_text()
        assert "SUBSCRIPTION_ID" in content
        assert "RESOURCE_GROUP" in content
        assert "WORKSPACE_NAME" in content
        assert "FOUNDRY_PROJECT_ENDPOINT" in content
        assert "FOUNDRY_MODEL" in content

    def test_has_smoke_test(self):
        content = (ASSETS_DIR / "deploy.sh").read_text()
        assert "smoke test" in content.lower()


class TestSkillMd:
    """Validate SKILL.md structure."""

    def test_skill_md_exists(self):
        skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
        assert skill_md.exists()

    def test_has_frontmatter(self):
        skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert content.startswith("---")
        # Should have closing frontmatter
        assert content.count("---") >= 2

    def test_frontmatter_has_name(self):
        skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert "name: maf-online-endpoint" in content

    def test_frontmatter_has_description(self):
        skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert "description:" in content


class TestReferences:
    """Validate reference documents exist."""

    REFS_DIR = Path(__file__).resolve().parent.parent / "references"

    def test_managed_identity_md(self):
        assert (self.REFS_DIR / "managed-identity.md").exists()

    def test_safe_rollout_md(self):
        assert (self.REFS_DIR / "safe-rollout.md").exists()

    def test_troubleshooting_md(self):
        assert (self.REFS_DIR / "troubleshooting.md").exists()
