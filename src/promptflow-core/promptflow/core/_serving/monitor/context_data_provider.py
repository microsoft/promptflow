# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from abc import ABC, abstractmethod

from promptflow.core._serving.flow_result import FlowResult


class ContextDataProvider(ABC):
    """Provides context data for monitor."""

    @abstractmethod
    def get_request_data(self):
        """Get context data for monitor."""
        pass

    @abstractmethod
    def get_request_start_time(self):
        """Get request start time."""
        pass

    @abstractmethod
    def get_request_id(self):
        """Get request id."""
        pass

    @abstractmethod
    def get_client_request_id(self):
        """Get client request id."""
        pass

    @abstractmethod
    def get_flow_id(self):
        """Get flow id."""
        pass

    @abstractmethod
    def get_flow_result(self) -> FlowResult:
        """Get flow result."""
        pass

    @abstractmethod
    def is_response_streaming(self) -> bool:
        """Get streaming."""
        pass

    @abstractmethod
    def get_exception_code(self):
        """Get flow execution exception code."""
        pass
