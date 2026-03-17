"""Unit tests for MiniMax integration with prompt flow.

These tests verify the MiniMax configuration, connection setup, and example flow
without requiring a live API key.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the example directory to path so we can import flow module
EXAMPLE_DIR = Path(__file__).absolute().parents[2] / "examples" / "flex-flows" / "chat-with-minimax"
sys.path.insert(0, str(EXAMPLE_DIR))


class TestMiniMaxConstants:
    """Test MiniMax configuration constants."""

    def test_minimax_base_url(self):
        from flow import MINIMAX_BASE_URL
        assert MINIMAX_BASE_URL == "https://api.minimax.io/v1"

    def test_minimax_models_defined(self):
        from flow import MINIMAX_MODELS
        assert "MiniMax-M2.5" in MINIMAX_MODELS
        assert "MiniMax-M2.5-highspeed" in MINIMAX_MODELS

    def test_minimax_models_have_descriptions(self):
        from flow import MINIMAX_MODELS
        for model, desc in MINIMAX_MODELS.items():
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestTemperatureClamping:
    """Test temperature value clamping for MiniMax API compatibility."""

    def test_clamp_normal_value(self):
        from flow import _clamp_temperature
        assert _clamp_temperature(0.5) == 0.5

    def test_clamp_zero(self):
        from flow import _clamp_temperature
        assert _clamp_temperature(0.0) == 0.0

    def test_clamp_one(self):
        from flow import _clamp_temperature
        assert _clamp_temperature(1.0) == 1.0

    def test_clamp_above_max(self):
        from flow import _clamp_temperature
        assert _clamp_temperature(1.5) == 1.0

    def test_clamp_below_min(self):
        from flow import _clamp_temperature
        assert _clamp_temperature(-0.5) == 0.0

    def test_clamp_very_large(self):
        from flow import _clamp_temperature
        assert _clamp_temperature(100.0) == 1.0

    def test_clamp_boundary_values(self):
        from flow import _clamp_temperature
        assert _clamp_temperature(0.001) == 0.001
        assert _clamp_temperature(0.999) == 0.999


class TestGetMiniMaxConfig:
    """Test the get_minimax_config helper function."""

    def test_config_with_explicit_api_key(self):
        from flow import get_minimax_config
        config = get_minimax_config(api_key="test-key")
        assert config.api_key == "test-key"
        assert config.base_url == "https://api.minimax.io/v1"
        assert config.model == "MiniMax-M2.5"

    def test_config_with_env_api_key(self):
        from flow import get_minimax_config
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "env-test-key"}):
            config = get_minimax_config()
            assert config.api_key == "env-test-key"

    def test_config_missing_api_key_raises(self):
        from flow import get_minimax_config
        with patch.dict(os.environ, {}, clear=True):
            # Remove MINIMAX_API_KEY if present
            os.environ.pop("MINIMAX_API_KEY", None)
            with pytest.raises(ValueError, match="MiniMax API key is required"):
                get_minimax_config()

    def test_config_custom_model(self):
        from flow import get_minimax_config
        config = get_minimax_config(model="MiniMax-M2.5-highspeed", api_key="test-key")
        assert config.model == "MiniMax-M2.5-highspeed"

    def test_config_base_url_always_set(self):
        from flow import get_minimax_config, MINIMAX_BASE_URL
        config = get_minimax_config(api_key="test-key")
        assert config.base_url == MINIMAX_BASE_URL


class TestChatFlowInit:
    """Test ChatFlow initialization."""

    def test_chatflow_init(self):
        from flow import ChatFlow, get_minimax_config
        config = get_minimax_config(api_key="test-key")
        flow = ChatFlow(config)
        assert flow.model_config == config
        assert flow.max_total_token == 4096

    def test_chatflow_custom_max_tokens(self):
        from flow import ChatFlow, get_minimax_config
        config = get_minimax_config(api_key="test-key")
        flow = ChatFlow(config, max_total_token=2048)
        assert flow.max_total_token == 2048


class TestConnectionYaml:
    """Test the MiniMax connection YAML configuration."""

    def test_connection_yaml_exists(self):
        conn_file = Path(__file__).absolute().parents[2] / "examples" / "connections" / "minimax.yml"
        assert conn_file.exists()

    def test_connection_yaml_content(self):
        import yaml
        conn_file = Path(__file__).absolute().parents[2] / "examples" / "connections" / "minimax.yml"
        with open(conn_file) as f:
            data = yaml.safe_load(f)
        assert data["name"] == "minimax_connection"
        assert data["type"] == "open_ai"
        assert data["base_url"] == "https://api.minimax.io/v1"


class TestFlowYaml:
    """Test the MiniMax flow YAML configuration."""

    def test_flow_yaml_exists(self):
        flow_file = EXAMPLE_DIR / "flow.flex.yaml"
        assert flow_file.exists()

    def test_flow_yaml_content(self):
        import yaml
        flow_file = EXAMPLE_DIR / "flow.flex.yaml"
        with open(flow_file) as f:
            data = yaml.safe_load(f)
        assert data["entry"] == "flow:ChatFlow"
        assert data["sample"]["init"]["model_config"]["model"] == "MiniMax-M2.5"


class TestPromptyTemplate:
    """Test the MiniMax prompty template."""

    def test_prompty_exists(self):
        prompty_file = EXAMPLE_DIR / "chat.prompty"
        assert prompty_file.exists()

    def test_prompty_contains_minimax_config(self):
        prompty_file = EXAMPLE_DIR / "chat.prompty"
        content = prompty_file.read_text()
        assert "MiniMax-M2.5" in content
        assert "https://api.minimax.io/v1" in content
        assert "openai" in content.lower()


class TestDocumentation:
    """Test that MiniMax documentation exists and is properly linked."""

    def test_doc_exists(self):
        doc_file = Path(__file__).absolute().parents[2] / "docs" / "integrations" / "llms" / "minimax.md"
        assert doc_file.exists()

    def test_doc_content(self):
        doc_file = Path(__file__).absolute().parents[2] / "docs" / "integrations" / "llms" / "minimax.md"
        content = doc_file.read_text()
        assert "MiniMax" in content
        assert "MiniMax-M2.5" in content
        assert "api.minimax.io" in content

    def test_doc_index_includes_minimax(self):
        index_file = Path(__file__).absolute().parents[2] / "docs" / "integrations" / "llms" / "index.md"
        content = index_file.read_text()
        assert "minimax" in content


class TestOpenAIConnectionWithMiniMax:
    """Test that OpenAIConnection works with MiniMax configuration."""

    def test_openai_connection_accepts_minimax_base_url(self):
        from promptflow.connections import OpenAIConnection
        conn = OpenAIConnection(
            api_key="test-key",
            base_url="https://api.minimax.io/v1",
        )
        assert conn.api_key == "test-key"
        assert conn.base_url == "https://api.minimax.io/v1"

    def test_openai_connection_normalize_config(self):
        from promptflow.connections import OpenAIConnection
        from promptflow.tools.common import normalize_connection_config
        conn = OpenAIConnection(
            api_key="test-key",
            base_url="https://api.minimax.io/v1",
        )
        config = normalize_connection_config(conn)
        assert config["api_key"] == "test-key"
        assert config["base_url"] == "https://api.minimax.io/v1"
        assert config["max_retries"] == 0

    def test_openai_model_config_with_minimax(self):
        from promptflow.core import OpenAIModelConfiguration
        config = OpenAIModelConfiguration(
            model="MiniMax-M2.5",
            base_url="https://api.minimax.io/v1",
            api_key="test-key",
        )
        assert config.model == "MiniMax-M2.5"
        assert config.base_url == "https://api.minimax.io/v1"
        assert config.api_key == "test-key"
