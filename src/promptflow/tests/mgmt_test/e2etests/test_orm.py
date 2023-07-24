# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import json
import uuid

import pytest

from promptflow.sdk._constants import RunStatus, RunTypes
from promptflow.sdk._orm import RunInfo
from promptflow.sdk.exceptions import RunNotFoundError


@pytest.fixture()
def run_name() -> str:
    name = str(uuid.uuid4())
    run_info = RunInfo(
        name=name,
        type=RunTypes.BATCH,
        created_on=datetime.datetime.now().isoformat(),
        status=RunStatus.NOT_STARTED,
        display_name=name,
        description="",
        tags=None,
        properties=json.dumps({}),
    )
    run_info.dump()
    return name


@pytest.mark.community_control_plane_sdk_test
@pytest.mark.e2etest
class TestRunInfo:
    def test_get(self, run_name: str) -> None:
        run_info = RunInfo.get(run_name)
        assert run_info.name == run_name
        assert run_info.type == RunTypes.BATCH
        assert run_info.status == RunStatus.NOT_STARTED
        assert run_info.display_name == run_name
        assert run_info.description == ""
        assert run_info.tags is None
        assert run_info.properties == json.dumps({})

    def test_get_not_exist(self) -> None:
        not_exist_name = str(uuid.uuid4())
        with pytest.raises(RunNotFoundError) as excinfo:
            RunInfo.get(not_exist_name)
        assert f"Run name {not_exist_name!r} cannot be found." in str(excinfo.value)

    def test_archive(self, run_name: str) -> None:
        run_info = RunInfo.get(run_name)
        assert run_info.archived is False
        run_info.archive()
        # in-memory archived flag
        assert run_info.archived is True
        # db archived flag
        assert RunInfo.get(run_name).archived is True

    def test_restore(self, run_name: str) -> None:
        run_info = RunInfo.get(run_name)
        run_info.archive()
        run_info = RunInfo.get(run_name)
        assert run_info.archived is True
        run_info.restore()
        # in-memory archived flag
        assert run_info.archived is False
        # db archived flag
        assert RunInfo.get(run_name).archived is False

    def test_update(self, run_name: str) -> None:
        run_info = RunInfo.get(run_name)
        assert run_info.status == RunStatus.NOT_STARTED
        assert run_info.display_name == run_name
        assert run_info.description == ""
        assert run_info.tags is None
        updated_status = RunStatus.COMPLETED
        updated_display_name = f"updated_{run_name}"
        updated_description = "updated_description"
        updated_tags = [{"key1": "value1", "key2": "value2"}]
        run_info.update(
            status=updated_status,
            display_name=updated_display_name,
            description=updated_description,
            tags=updated_tags,
        )
        # in-memory status, display_name, description and tags
        assert run_info.status == updated_status
        assert run_info.display_name == updated_display_name
        assert run_info.description == updated_description
        assert run_info.tags == json.dumps(updated_tags)
        # db status, display_name, description and tags
        run_info = RunInfo.get(run_name)
        assert run_info.status == updated_status
        assert run_info.display_name == updated_display_name
        assert run_info.description == updated_description
        assert run_info.tags == json.dumps(updated_tags)

    def test_null_type_and_display_name(self) -> None:
        # test run_info table schema change:
        # 1. type can be null(we will deprecate this concept in the future)
        # 2. display_name can be null as default value
        name = str(uuid.uuid4())
        run_info = RunInfo(
            name=name,
            created_on=datetime.datetime.now().isoformat(),
            status=RunStatus.NOT_STARTED,
            description="",
            tags=None,
            properties=json.dumps({}),
        )
        run_info.dump()
        run_info_from_db = RunInfo.get(name)
        assert run_info_from_db.type is None
        assert run_info_from_db.display_name is None
