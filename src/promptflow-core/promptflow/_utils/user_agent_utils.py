import os
from typing import Optional

from promptflow._constants import PF_USER_AGENT, USER_AGENT
from promptflow._utils.logger_utils import LoggerFactory
from promptflow.core._version import __version__
from promptflow.tracing._operation_context import OperationContext

logger = LoggerFactory.get_logger(__name__)


class ClientUserAgentUtil:
    """SDK/CLI side user agent utilities."""

    @classmethod
    def _get_context(cls):
        return OperationContext.get_instance()

    @classmethod
    def get_user_agent(cls):
        context = cls._get_context()
        # directly get from context since client side won't need promptflow/xxx.
        return context.get(OperationContext.USER_AGENT_KEY, "").strip()

    @classmethod
    def append_user_agent(cls, user_agent: Optional[str]):
        if not user_agent:
            return
        context = cls._get_context()
        context.append_user_agent(user_agent)

    @classmethod
    def update_user_agent_from_env_var(cls):
        # this is for backward compatibility: we should use PF_USER_AGENT in newer versions.
        for env_name in [USER_AGENT, PF_USER_AGENT]:
            if env_name in os.environ:
                cls.append_user_agent(os.environ[env_name])

    @classmethod
    def update_user_agent_from_config(cls):
        """Update user agent from config. 1p customer will set it. We'll add PFCustomer_ as prefix."""
        try:
            from promptflow._sdk._configuration import Configuration

            config = Configuration.get_instance()
            user_agent = config.get_user_agent()
            if user_agent:
                cls.append_user_agent(user_agent)
        except ImportError as e:
            # Ignore if promptflow-devkit not installed, then config is not available.
            logger.debug(f"promptflow-devkit not installed, skip update_user_agent_from_config. Exception {e}")
            pass


def setup_user_agent_to_operation_context(user_agent):
    """Setup user agent to OperationContext.
    For calls from extension, ua will be like: prompt-flow-extension/ promptflow-cli/ promptflow-sdk/
    For calls from CLI, ua will be like: promptflow-cli/ promptflow-sdk/
    For calls from SDK, ua will be like: promptflow-sdk/
    For 1p customer call which set user agent in config, ua will be like: PFCustomer_XXX/
    For serving with promptflow-core only env, ua will be like: promptflow-local-serving/ promptflow-core/
    """
    # add user added UA after SDK/CLI
    ClientUserAgentUtil.append_user_agent(user_agent)
    ClientUserAgentUtil.update_user_agent_from_env_var()
    ClientUserAgentUtil.update_user_agent_from_config()
    return ClientUserAgentUtil.get_user_agent()


def append_promptflow_package_ua(operation_context: OperationContext):
    try:
        from promptflow._version import VERSION as PF_VERSION

        operation_context.append_user_agent(f"promptflow/{PF_VERSION}")
    except ImportError:
        pass
    operation_context.append_user_agent(f"promptflow-core/{__version__}")
