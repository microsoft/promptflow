# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import hashlib
import os
from os import PathLike
from pathlib import Path
from typing import Union


def get_flow_session_id(flow_dir: Union[str, PathLike]):
    """
    Get the flow session id from flow. The flow id will be same for same flow in same GIT repo or device.
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
        session_id = f"{os.path.basename(repo.working_dir)}/{flow_dir.relative_to(repo.working_dir).as_posix()}"

    except Exception:
        # failed to get repo, use device id + absolute path to flow_dir as session id
        import uuid

        device_id = uuid.getnode()
        session_id = f"{device_id}/{flow_dir.absolute().as_posix()}"

    # hash the value to avoid it gets too long, and it's not user visible.
    session_id = hashlib.sha256(session_id.encode()).hexdigest()
    return session_id
