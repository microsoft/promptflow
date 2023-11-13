# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import hashlib
import os
from os import PathLike
from pathlib import Path
from typing import Any, Dict, List, Mapping, Union

from promptflow._sdk._logger_factory import LoggerFactory
from promptflow.contracts.flow import FlowInputDefinition
from promptflow.contracts.run_info import FlowRunInfo, Status

logger = LoggerFactory.get_logger(name=__name__)


def get_flow_lineage_id(flow_dir: Union[str, PathLike]):
    """
    Get the lineage id for flow. The flow lineage id will be same for same flow in same GIT repo or device.
    If the flow locates in GIT repo:
        use Repo name + relative path to flow_dir as session id
    Otherwise:
        use device id + absolute path to flow_dir as session id
    :param flow_dir: flow directory
    """
    flow_dir = Path(flow_dir).resolve()
    if not flow_dir.is_dir():
        flow_dir = flow_dir.parent
    try:
        from git import Repo

        repo = Repo(flow_dir, search_parent_directories=True)
        lineage_id = f"{os.path.basename(repo.working_dir)}/{flow_dir.relative_to(repo.working_dir).as_posix()}"
        logger.debug("Got lineage id %s from git repo.", lineage_id)

    except Exception:
        # failed to get repo, use device id + absolute path to flow_dir as session id
        import uuid

        device_id = uuid.getnode()
        lineage_id = f"{device_id}/{flow_dir.absolute().as_posix()}"
        logger.debug("Got lineage id %s from local since failed to get git info.", lineage_id)

    # hash the value to avoid it gets too long, and it's not user visible.
    lineage_id = hashlib.sha256(lineage_id.encode()).hexdigest()
    return lineage_id


def apply_default_value_for_input(inputs: Dict[str, FlowInputDefinition], line_inputs: Mapping) -> Dict[str, Any]:
    updated_inputs = dict(line_inputs or {})
    for key, value in inputs.items():
        if key not in updated_inputs and (value and value.default):
            updated_inputs[key] = value.default
    return updated_inputs


def handle_line_failures(run_infos: List[FlowRunInfo], raise_on_line_failure: bool = False):
    """Handle line failures in batch run"""
    failed = [i for i, r in enumerate(run_infos) if r.status == Status.Failed]
    failed_msg = None
    if len(failed) > 0:
        failed_indexes = ",".join([str(i) for i in failed])
        first_fail_exception = run_infos[failed[0]].error["message"]
        if raise_on_line_failure:
            failed_msg = "Flow run failed due to the error: " + first_fail_exception
            raise Exception(failed_msg)

        failed_msg = (
            f"{len(failed)}/{len(run_infos)} flow run failed, indexes: [{failed_indexes}],"
            f" exception of index {failed[0]}: {first_fail_exception}"
        )
        logger.error(failed_msg)
