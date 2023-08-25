# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from threading import Lock

from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller


class _FlowServiceCallerFactory:

    caller_cache_by_workspace_id = {}
    _instance_lock = Lock()

    @classmethod
    def get_instance(cls, workspace, credential, region=None, **kwargs) -> FlowServiceCaller:
        """Get instance of flow service caller.

        :param workspace: workspace
        """
        catch_id = workspace.id if workspace else region
        cache = cls.caller_cache_by_workspace_id
        if catch_id not in cache:
            with _FlowServiceCallerFactory._instance_lock:
                if catch_id not in cache:
                    cache[catch_id] = FlowServiceCaller(workspace, credential=credential, region=region, **kwargs)

        return cache[catch_id]
