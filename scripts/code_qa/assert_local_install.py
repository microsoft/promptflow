"""Tests checking that azure packages are NOT installed."""
import importlib
import pytest


class TestPackagesNotInstalles():
    """Test imports."""

    @pytest.mark.parametrize('package', [
        'promptflow.azure',
        'azure.ai.ml',
        'azure.storage.blob'
    ])
    def test_promptflow_azure(self, package):
        """Test promptflow. azure is not installed."""
        try:
            importlib.import_module(package)
            assert False, f'Package {package} must be uninstalled for local test.'
        except (ModuleNotFoundError, ImportError):
            pass
