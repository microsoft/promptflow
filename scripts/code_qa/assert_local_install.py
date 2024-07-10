"""Tests checking that azure packages are NOT installed."""
import importlib
import pytest


class TestPackagesNotInstalles():
    """Test imports."""

    @pytest.mark.parametrize('package', [
        'promptflow.azure',
        'azure.ai.ml',
        'azure.identity',
        'azure.storage.blob'
    ])
    def test_promptflow_azure(self, package):
        """Test promptflow. azure is not installed."""
        assert importlib.util.find_spec(package) is None, f'Package {package} must be uninstalled for local test.'
