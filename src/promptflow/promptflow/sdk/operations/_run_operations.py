# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from promptflow.sdk._constants import (
    MAX_RUN_LIST_RESULTS,
    FlowRunProperties,
    ListViewType,
    LocalStorageFilenames,
    RunStatus,
    RunTypes,
    VisualizeDetailConstants,
)
from promptflow.sdk._orm import RunInfo as ORMRun
from promptflow.sdk._utils import incremental_print, parse_variant, render_jinja_template, safe_parse_object_list
from promptflow.sdk._visualize_functions import dump_html, generate_html_string
from promptflow.sdk.entities import Run
from promptflow.sdk.exceptions import InvalidRunStatusError, RunExistsError, RunNotFoundError
from promptflow.sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow.sdk.operations._run_submitter import RunSubmitter

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
        :rtype: List[~promptflow.sdk.entities.run.Run]
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
        :rtype: ~promptflow.sdk.entities.run.Run
        """
        try:
            return Run._from_orm_object(ORMRun.get(name))
        except RunNotFoundError as e:
            raise e

    def create_or_update(self, run: Run, **kwargs):
        """Create or update a run.

        :param run: Run object to create or update.
        :type run: ~promptflow.sdk.entities.run.Run
        :return: Run object created or updated.
        :rtype: ~promptflow.sdk.entities.run.Run
        """
        # TODO: change to async
        stream = kwargs.pop("stream", False)
        try:
            return RunSubmitter(run_operations=self).submit(run=run, stream=stream, **kwargs)
        except RunExistsError:
            raise RunExistsError(f"Run {run.name!r} already exists.")

    def stream(self, name: Union[str, Run]) -> None:
        """Stream run logs to the console.

        :param name: Name of the run, or run object.
        :type name: Union[str, ~promptflow.sdk.entities.Run]
        """
        run = name if isinstance(name, Run) else self.get(name=name)
        local_storage = LocalStorageOperations(run=run)

        file_handler = sys.stdout
        try:
            printed = 0
            run = self.get(run.name)
            while run.status in RUNNING_STATUSES or run.status == RunStatus.FINALIZING:
                file_handler.flush()
                available_logs = local_storage.get_logs()
                printed = incremental_print(available_logs, printed, file_handler)
                time.sleep(10)
                run = self.get(run.name)
            # ensure all logs are printed
            file_handler.flush()
            available_logs = local_storage.get_logs()
            incremental_print(available_logs, printed, file_handler)

            print("======= Run Summary =======\n")
            duration = str(run._end_time - run._created_on)
            print(
                f'Run name: "{run.name}"\n'
                f'Run status: "{run.status}"\n'
                f'Start time: "{run._created_on}"\n'
                f'Duration: "{duration}"'
            )
            if run.status == RunStatus.FAILED:
                error_message = local_storage.get_error_message()
                if error_message is not None:
                    print("\nError:")
                    print(json.dumps(error_message, indent=4))

        except KeyboardInterrupt:
            error_message = "The output streaming for the run was interrupted, but the run is still executing."
            print(error_message)

    def archive(self, name: str) -> None:
        """Archive a run.

        :param name: Name of the run.
        :type name: str
        """
        ORMRun.get(name).archive()

    def restore(self, name: str) -> None:
        """Restore a run.

        :param name: Name of the run.
        :type name: str
        """
        ORMRun.get(name).restore()

    def update(
        self,
        name: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> None:
        """Update run status.

        :param name: run name
        :param display_name: display name to update
        :param description: description to update
        :param tags: tags to update
        :param kwargs: other fields to update, fields not supported will be directly dropped.
        """
        # the kwargs is to support update run status scenario but keep it private
        ORMRun.get(name).update(display_name=display_name, description=description, tags=tags, **kwargs)

    def get_details(self, name: Union[str, Run]) -> pd.DataFrame:
        run = name if isinstance(name, Run) else self.get(name=name)
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
        local_storage = LocalStorageOperations(run=run)
        return local_storage.load_metrics()

    @staticmethod
    def _get_and_parse_io_spec(
        local_storage: LocalStorageOperations,
    ) -> Tuple[Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
        inputs_spec, outputs_spec = local_storage.load_io_spec()
        parsed_inputs_spec = {k: {"type": v["type"]} for k, v in inputs_spec.items()}
        parsed_outputs_spec = {k: {"type": v["type"]} for k, v in outputs_spec.items()}
        return parsed_inputs_spec, parsed_outputs_spec

    @staticmethod
    def _get_batch_run_variant_id(run: Run) -> str:
        # before we fully depreciate the concept of variant id, we still need to create it for UX display
        node_variant = run.properties.get(FlowRunProperties.NODE_VARIANT, None)
        return parse_variant(node_variant)[-1] if node_variant is not None else run.name

    def _get_and_parse_run_data(self, local_storage: LocalStorageOperations) -> List[Dict[str, Any]]:
        data = []
        run = local_storage._run
        inputs = local_storage.load_inputs()
        outputs = local_storage.load_outputs()
        lines = len(list(inputs.values())[0])
        for i in range(lines):
            current_input = {k: inputs[k][i] for k in inputs}
            current_output = {k: outputs[k][i] for k in outputs}
            if run.type == RunTypes.BATCH:
                variant_id = self._get_batch_run_variant_id(run)
            else:
                # eval run: follow batch run
                eval_batch_run = self.get(str(run.run))
                variant_id = self._get_batch_run_variant_id(eval_batch_run)
            current_data = {
                "run_id": run.name,
                "status": run.status,
                "inputs": current_input,
                "outputs": copy.deepcopy(current_output),
                "index": i,
                "variant_id": variant_id,
                "result": copy.deepcopy(current_output),
            }
            # insert variant_id in inputs for eval run
            if run.type == RunTypes.EVALUATION:
                current_data["inputs"]["variant_id"] = variant_id
            data.append(current_data)
        return data

    def _generate_data_for_detail_template(self, runs: List[Run]) -> Dict[str, Union[dict, list]]:
        # check run status first
        # if run status is not compeleted, there might be unexpected error during parse data
        # e.g. empty input(s)/output(s) line
        # so we directly raise error if there is any incomplete run
        for run in runs:
            if run.status != RunStatus.COMPLETED:
                error_message = (
                    f"Run {run.name!r} is not completed, "
                    "please wait for its completion, or select other completed run(s)."
                )
                raise InvalidRunStatusError(error_message)

        local_storages = {run.name: LocalStorageOperations(run) for run in runs}
        # TODO(2554051): new visualize contract, no need to differ run type
        # currently we still use old contract, so need to differ batch and evaluation
        # to differ them without type, we regard run with run against is old evaluation run
        bulk_runs, eval_runs = [], []
        for run in runs:
            if run.run:
                eval_runs.append(run)
            else:
                bulk_runs.append(run)
        # when only evaluation runs, we need to handle them as bulk runs
        if len(bulk_runs) == 0:
            bulk_runs = copy.deepcopy(eval_runs)
            eval_runs = []
        data = {}
        # bulk run input/output spec
        # TODO(zhengfeiwang): how to handle different spec(if exists)?
        data["input_spec"], data["output_spec"] = self._get_and_parse_io_spec(local_storages[bulk_runs[0].name])
        # bulk run data
        data["runs_data"] = []
        for bulk_run in bulk_runs:
            data["runs_data"] += self._get_and_parse_run_data(local_storages[bulk_run.name])
        # evaluate runs
        data["eval_runs"] = []
        for eval_run in eval_runs:
            eval_data = {"name": eval_run.name, "display_name": eval_run.display_name}
            eval_local_storage = local_storages[eval_run.name]
            # evaluate run input/output spec
            eval_data["input_spec"], eval_data["output_spec"] = self._get_and_parse_io_spec(eval_local_storage)
            # evaluate run data
            eval_data["runs_data"] = self._get_and_parse_run_data(local_storages[eval_run.name])
            data["eval_runs"].append(eval_data)
        return data

    def _visualize(self, runs: List[Run], html_path: Optional[str] = None) -> None:
        data = self._generate_data_for_detail_template(runs)
        yaml_string = render_jinja_template(VisualizeDetailConstants.JINJA2_TEMPLATE, **data)
        html_string = generate_html_string(yaml_string)
        # if html_path is specified, not open it in webbrowser(as it comes from VSC)
        dump_html(html_string, html_path, open_html=html_path is None)

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
    def get_outputs(cls, run: Union[str, Run]) -> List[Dict[str, Any]]:
        """Get the outputs of the run, load from local storage."""
        if isinstance(run, str):
            run = cls.get(name=run)
        local_storage = LocalStorageOperations(run)
        return local_storage.load_outputs()

    @classmethod
    def get_inputs(cls, run: Union[str, Run]) -> List[Dict[str, Any]]:
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
