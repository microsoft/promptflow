# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from promptflow._sdk._constants import (
    MAX_RUN_LIST_RESULTS,
    ListViewType,
    LocalStorageFilenames,
    RunStatus,
)
from promptflow._sdk._orm import RunInfo as ORMRun
from promptflow._sdk._utils import incremental_print, safe_parse_object_list
from promptflow._sdk._visualize_functions import dump_html, generate_html_string
from promptflow._sdk.entities import Run
from promptflow._sdk.exceptions import RunExistsError, RunNotFoundError
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow.contracts.run_management import RunMetadata, RunVisualization

RUNNING_STATUSES = RunStatus.get_running_statuses()


class RunOperations:
    """RunOperations."""

    def __init__(self):
        pass

    def list(
        self,
        max_results: Optional[int] = MAX_RUN_LIST_RESULTS,
        *,
        list_view_type: ListViewType = ListViewType.ACTIVE_ONLY,
    ) -> List[Run]:
        """List runs locally.

        :param max_results: Max number of results to return. Default: MAX_RUN_LIST_RESULTS.
        :type max_results: Optional[int]
        :param list_view_type: View type for including/excluding (for example) archived runs. Default: ACTIVE_ONLY.
        :type include_archived: Optional[ListViewType]
        :return: List of run objects.
        :rtype: List[~promptflow.entities.Run]
        """
        orm_runs = ORMRun.list(max_results=max_results, list_view_type=list_view_type)
        return safe_parse_object_list(
            obj_list=orm_runs,
            parser=Run._from_orm_object,
            message_generator=lambda x: f"Error parsing run {x.name!r}, skipped.",
        )

    @classmethod
    def get(cls, name: str) -> Run:
        """Get a run entity.

        :param name: Name of the run.
        :type name: str
        :return: run object retrieved from the database.
        :rtype: ~promptflow.entities.Run
        """
        try:
            return Run._from_orm_object(ORMRun.get(name))
        except RunNotFoundError as e:
            raise e

    def create_or_update(self, run: Run, **kwargs) -> Run:
        """Create or update a run.

        :param run: Run object to create or update.
        :type run: ~promptflow.entities.Run
        :return: Run object created or updated.
        :rtype: ~promptflow.entities.Run
        """
        # TODO: change to async
        stream = kwargs.pop("stream", False)
        try:
            from promptflow._sdk.operations._run_submitter import RunSubmitter

            created_run = RunSubmitter(run_operations=self).submit(run=run, **kwargs)
            if stream:
                self.stream(created_run)
            return created_run
        except RunExistsError:
            raise RunExistsError(f"Run {run.name!r} already exists.")

    def _print_run_summary(self, run: Run) -> None:
        print("======= Run Summary =======\n")
        duration = str(run._end_time - run._created_on)
        print(
            f'Run name: "{run.name}"\n'
            f'Run status: "{run.status}"\n'
            f'Start time: "{run._created_on}"\n'
            f'Duration: "{duration}"\n'
            f'Output path: "{run._output_path}"\n'
        )

    def stream(self, name: Union[str, Run]) -> Run:
        """Stream run logs to the console.

        :param name: Name of the run, or run object.
        :type name: Union[str, ~promptflow.sdk.entities.Run]
        :return: Run object.
        :rtype: ~promptflow.entities.Run
        """
        run = name if isinstance(name, Run) else self.get(name=name)
        local_storage = LocalStorageOperations(run=run)

        file_handler = sys.stdout
        try:
            printed = 0
            run = self.get(run.name)
            while run.status in RUNNING_STATUSES or run.status == RunStatus.FINALIZING:
                file_handler.flush()
                available_logs = local_storage.logger.get_logs()
                printed = incremental_print(available_logs, printed, file_handler)
                time.sleep(10)
                run = self.get(run.name)
            # ensure all logs are printed
            file_handler.flush()
            available_logs = local_storage.logger.get_logs()
            incremental_print(available_logs, printed, file_handler)
            self._print_run_summary(run)
            # won't print error here, put it in run dict
        except KeyboardInterrupt:
            error_message = "The output streaming for the run was interrupted, but the run is still executing."
            print(error_message)
        finally:
            return run

    def archive(self, name: str) -> Run:
        """Archive a run.

        :param name: Name of the run.
        :type name: str
        :return: archived run object.
        :rtype: ~promptflow._sdk.entities._run.Run
        """
        ORMRun.get(name).archive()
        return self.get(name)

    def restore(self, name: str) -> Run:
        """Restore a run.

        :param name: Name of the run.
        :type name: str
        :return: restored run object.
        :rtype: ~promptflow._sdk.entities._run.Run
        """
        ORMRun.get(name).restore()
        return self.get(name)

    def update(
        self,
        name: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Run:
        """Update run status.

        :param name: run name
        :param display_name: display name to update
        :param description: description to update
        :param tags: tags to update
        :param kwargs: other fields to update, fields not supported will be directly dropped.
        :return: updated run object
        :rtype: ~promptflow._sdk.entities._run.Run
        """
        # the kwargs is to support update run status scenario but keep it private
        ORMRun.get(name).update(
            display_name=display_name, description=description, tags=tags, **kwargs
        )
        return self.get(name)

    def get_details(self, name: Union[str, Run]) -> pd.DataFrame:
        run = name if isinstance(name, Run) else self.get(name=name)
        run._check_run_status_is_completed()
        local_storage = LocalStorageOperations(run=run)
        inputs = local_storage.load_inputs()
        outputs = local_storage.load_outputs()
        data = {}
        columns = []
        for k in inputs:
            new_k = f"inputs.{k}"
            data[new_k] = copy.deepcopy(inputs[k])
            columns.append(new_k)
        for k in outputs:
            new_k = f"outputs.{k}"
            data[new_k] = copy.deepcopy(outputs[k])
            columns.append(new_k)
        df = pd.DataFrame(data).reindex(columns=columns)
        return df

    def get_metrics(self, name: Union[str, Run]) -> Dict[str, Any]:
        run = name if isinstance(name, Run) else self.get(name=name)
        run._check_run_status_is_completed()
        local_storage = LocalStorageOperations(run=run)
        return local_storage.load_metrics()

    def _visualize(self, runs: List[Run], html_path: Optional[str] = None) -> None:
        details, metadatas = [], []
        for run in runs:
            # check run status first
            # if run status is not compeleted, there might be unexpected error during parse data
            # so we directly raise error if there is any incomplete run
            run._check_run_status_is_completed()

            local_storage = LocalStorageOperations(run)
            detail = local_storage.load_detail()
            metadata = RunMetadata(
                name=run.name,
                display_name=run.display_name,
                tags=run.tags,
                lineage=run.run,
            )
            details.append(copy.deepcopy(detail))
            metadatas.append(asdict(metadata))
        data_for_visualize = RunVisualization(detail=details, metadata=metadatas)
        html_string = generate_html_string(asdict(data_for_visualize))
        # if html_path is specified, not open it in webbrowser(as it comes from VSC)
        dump_html(html_string, html_path=html_path, open_html=html_path is None)

    def visualize(self, runs: Union[str, Run, List[str], List[Run]], **kwargs) -> None:
        """Visualize run(s).

        :param runs: List of run objects, or names of the runs.
        :type runs: Union[str, ~promptflow.sdk.entities.Run, List[str], List[~promptflow.sdk.entities.Run]]
        """
        if not isinstance(runs, list):
            runs = [runs]
        if not isinstance(runs[0], Run):
            runs = [self.get(name) for name in runs]
        html_path = kwargs.pop("html_path", None)
        self._visualize(runs, html_path=html_path)

    @classmethod
    def _get_outputs(cls, run: Union[str, Run]) -> List[Dict[str, Any]]:
        """Get the outputs of the run, load from local storage."""
        if isinstance(run, str):
            run = cls.get(name=run)
        local_storage = LocalStorageOperations(run)
        return local_storage.load_outputs()

    @classmethod
    def _get_inputs(cls, run: Union[str, Run]) -> List[Dict[str, Any]]:
        """Get the outputs of the run, load from local storage."""
        if isinstance(run, str):
            run = cls.get(name=run)
        local_storage = LocalStorageOperations(run)
        return local_storage.load_inputs()

    @classmethod
    def _get_details(cls, run: Run) -> Any:
        try:
            with open(Path(run._output_path) / LocalStorageFilenames.DETAIL, "r") as f:
                return json.load(f)
        except Exception as e:
            raise Exception(f"Failed to load details for run {run}") from e
