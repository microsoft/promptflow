# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import os.path
import sys
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Union

from promptflow._constants import LANGUAGE_KEY, AvailableIDE, FlowLanguage, FlowType
from promptflow._sdk._constants import (
    MAX_RUN_LIST_RESULTS,
    MAX_SHOW_DETAILS_RESULTS,
    FlowRunProperties,
    ListViewType,
    LocalStorageFilenames,
    RunInfoSources,
    RunMode,
    RunStatus,
)
from promptflow._sdk._errors import (
    InvalidRunStatusError,
    PromptFlowServiceInvocationError,
    RunExistsError,
    RunNotFoundError,
    RunOperationParameterError,
)
from promptflow._sdk._orm import RunInfo as ORMRun
from promptflow._sdk._service.utils.utils import is_pfs_service_healthy
from promptflow._sdk._telemetry import ActivityType, TelemetryMixin, monitor_operation
from promptflow._sdk._tracing import _invoke_pf_svc
from promptflow._sdk._utilities.general_utils import incremental_print, print_red_error, safe_parse_object_list
from promptflow._sdk._visualize_functions import dump_html, generate_html_string, generate_trace_ui_html_string
from promptflow._sdk.entities import Run
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.yaml_utils import load_yaml, load_yaml_string
from promptflow.contracts._run_management import RunDetail, RunMetadata, RunVisualization, VisualizationConfig
from promptflow.exceptions import UserErrorException

RUNNING_STATUSES = RunStatus.get_running_statuses()

logger = get_cli_sdk_logger()


class RunOperations(TelemetryMixin):
    """RunOperations."""

    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self._client = client

    @monitor_operation(activity_name="pf.runs.list", activity_type=ActivityType.PUBLICAPI)
    def list(
        self,
        max_results: Optional[int] = MAX_RUN_LIST_RESULTS,
        *,
        list_view_type: ListViewType = ListViewType.ACTIVE_ONLY,
    ) -> List[Run]:
        """List runs.

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

    @monitor_operation(activity_name="pf.runs.search", activity_type=ActivityType.INTERNALCALL)
    def _search(
        self,
        search_name: str,
        max_results: Optional[int] = MAX_RUN_LIST_RESULTS,
    ) -> List[Run]:
        """List runs.

        :param search_name: The search name prefix.
        :type search_name: str
        :param max_results: Max number of results to return. Default: MAX_RUN_LIST_RESULTS.
        :type max_results: Optional[int]
        :return: List of run objects.
        :rtype: List[~promptflow.entities.Run]
        """
        orm_runs = ORMRun.search(search_name=search_name, max_results=max_results)
        return safe_parse_object_list(
            obj_list=orm_runs,
            parser=Run._from_orm_object,
            message_generator=lambda x: f"Error parsing run {x.name!r}, skipped.",
        )

    @monitor_operation(activity_name="pf.runs.get", activity_type=ActivityType.PUBLICAPI)
    def get(self, name: str) -> Run:
        """Get a run entity.

        :param name: Name of the run.
        :type name: str
        :return: run object retrieved from the database.
        :rtype: ~promptflow.entities.Run
        """
        return self._get(name)

    def _get(self, name: str) -> Run:
        name = Run._validate_and_return_run_name(name)
        try:
            return Run._from_orm_object(ORMRun.get(name))
        except RunNotFoundError as e:
            raise e

    @monitor_operation(activity_name="pf.runs.create_or_update", activity_type=ActivityType.PUBLICAPI)
    def create_or_update(self, run: Run, **kwargs) -> Run:
        """Create or update a run.

        :param run: Run object to create or update.
        :type run: ~promptflow.entities.Run
        :return: Run object created or updated.
        :rtype: ~promptflow.entities.Run
        """
        # create run from an existing run folder
        if run._run_source == RunInfoSources.EXISTING_RUN:
            return self._create_run_from_existing_run_folder(run=run, **kwargs)
        # TODO: change to async
        stream = kwargs.pop("stream", False)
        try:
            from promptflow._sdk._orchestrator import RunSubmitter

            created_run = RunSubmitter(client=self._client).submit(run=run, **kwargs)
            if stream:
                self.stream(created_run)
            return created_run
        except RunExistsError:
            raise RunExistsError(f"Run {run.name!r} already exists.")

    @monitor_operation(activity_name="pf.runs.resume", activity_type=ActivityType.PUBLICAPI)
    def _create_by_resume_from(self, resume_from: str, **kwargs) -> Run:
        """Create a run by the resume_from run, a new run will be created to rerun failed lines.

        :param resume_from: Run name to resume from.
        :type resume_from: str
        :return: Run object created based on an existing run.
        :rtype: ~promptflow.entities.Run
        """
        logger.debug(f"Resume from {resume_from!r}, kwargs: {kwargs}")
        stream = kwargs.pop("stream", False)
        from promptflow._sdk._orchestrator import RunSubmitter

        created_run = RunSubmitter(client=self._client).resume(resume_from=resume_from, **kwargs)
        if stream:
            self.stream(created_run)
        return created_run

    def _create_run_from_existing_run_folder(self, run: Run, **kwargs) -> Run:
        """Create run from existing run folder."""
        try:
            self.get(run.name)
        except RunNotFoundError:
            pass
        else:
            raise RunExistsError(f"Run {run.name!r} already exists.")

        try:
            run._dump()
            return run
        except Exception as e:
            raise UserErrorException(
                f"Failed to create run {run.name!r} from existing run folder {run.source!r}: {str(e)}"
            ) from e

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

    @monitor_operation(activity_name="pf.runs.stream", activity_type=ActivityType.PUBLICAPI)
    def stream(self, name: Union[str, Run], raise_on_error: bool = True) -> Run:
        """Stream run logs to the console.

        :param name: Name of the run, or run object.
        :type name: Union[str, ~promptflow.sdk.entities.Run]
        :param raise_on_error: Raises an exception if a run fails or canceled.
        :type raise_on_error: bool
        :return: Run object.
        :rtype: ~promptflow.entities.Run
        """
        name = Run._validate_and_return_run_name(name)
        run = self.get(name=name)
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
        except KeyboardInterrupt:
            error_message = "The output streaming for the run was interrupted, but the run is still executing."
            print(error_message)

        if run.status == RunStatus.FAILED or run.status == RunStatus.CANCELED:
            if run.status == RunStatus.FAILED:
                error_message = local_storage.load_exception().get("message", "Run fails with unknown error.")
            else:
                error_message = "Run is canceled."
            if raise_on_error:
                raise InvalidRunStatusError(error_message)
            else:
                print_red_error(error_message)

        return run

    @monitor_operation(activity_name="pf.runs.archive", activity_type=ActivityType.PUBLICAPI)
    def archive(self, name: Union[str, Run]) -> Run:
        """Archive a run.

        :param name: Name of the run.
        :type name: str
        :return: archived run object.
        :rtype: ~promptflow._sdk.entities._run.Run
        """
        name = Run._validate_and_return_run_name(name)
        ORMRun.get(name).archive()
        return self.get(name)

    @monitor_operation(activity_name="pf.runs.restore", activity_type=ActivityType.PUBLICAPI)
    def restore(self, name: Union[str, Run]) -> Run:
        """Restore a run.

        :param name: Name of the run.
        :type name: str
        :return: restored run object.
        :rtype: ~promptflow._sdk.entities._run.Run
        """
        name = Run._validate_and_return_run_name(name)
        ORMRun.get(name).restore()
        return self.get(name)

    @monitor_operation(activity_name="pf.runs.update", activity_type=ActivityType.PUBLICAPI)
    def update(
        self,
        name: Union[str, Run],
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
        name = Run._validate_and_return_run_name(name)
        # the kwargs is to support update run status scenario but keep it private
        ORMRun.get(name).update(display_name=display_name, description=description, tags=tags, **kwargs)
        return self.get(name)

    @monitor_operation(activity_name="pf.runs.delete", activity_type=ActivityType.PUBLICAPI)
    def delete(
        self,
        name: str,
    ) -> None:
        """Delete run permanently.
        Caution: This operation will delete the run permanently from your local disk.
        Both run entity and output data will be deleted.

        :param name: run name to delete
        :return: None
        """
        valid_run = self.get(name)
        LocalStorageOperations(valid_run).delete()
        ORMRun.delete(name)

    @monitor_operation(activity_name="pf.runs.get_details", activity_type=ActivityType.PUBLICAPI)
    def get_details(
        self, name: Union[str, Run], max_results: int = MAX_SHOW_DETAILS_RESULTS, all_results: bool = False
    ) -> "DataFrame":
        """Get the details from the run.

        .. note::

            If `all_results` is set to True, `max_results` will be overwritten to sys.maxsize.

        :param name: The run name or run object
        :type name: Union[str, ~promptflow.sdk.entities.Run]
        :param max_results: The max number of runs to return, defaults to 100
        :type max_results: int
        :param all_results: Whether to return all results, defaults to False
        :type all_results: bool
        :raises RunOperationParameterError: If `max_results` is not a positive integer.
        :return: The details data frame.
        :rtype: pandas.DataFrame
        """
        from pandas import DataFrame

        # if all_results is True, set max_results to sys.maxsize
        if all_results:
            max_results = sys.maxsize

        if not isinstance(max_results, int) or max_results < 1:
            raise RunOperationParameterError(f"'max_results' must be a positive integer, got {max_results!r}")

        name = Run._validate_and_return_run_name(name)
        run = self.get(name=name)
        local_storage = LocalStorageOperations(run=run)
        inputs, outputs = local_storage.load_inputs_and_outputs()
        inputs = inputs.to_dict("list")
        outputs = outputs.to_dict("list")
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
        df = DataFrame(data).head(max_results).reindex(columns=columns)
        return df

    @monitor_operation(activity_name="pf.runs.get_metrics", activity_type=ActivityType.PUBLICAPI)
    def get_metrics(self, name: Union[str, Run]) -> Dict[str, Any]:
        """Get run metrics.

        :param name: name of the run.
        :type name: str
        :return: Run metrics.
        :rtype: Dict[str, Any]
        """
        name = Run._validate_and_return_run_name(name)
        run = self.get(name=name)
        run._check_run_status_is_completed()
        local_storage = LocalStorageOperations(run=run)
        return local_storage.load_metrics()

    def _visualize(self, runs: List[Run], html_path: Optional[str] = None) -> None:
        details: List[RunDetail] = []
        metadatas: List[RunMetadata] = []
        configs: List[VisualizationConfig] = []
        for run in runs:
            # check run status first
            # if run status is not compeleted, there might be unexpected error during parse data
            # so we directly raise error if there is any incomplete run
            run._check_run_status_is_completed()

            local_storage = LocalStorageOperations(run)
            # nan, inf and -inf are not JSON serializable, which will lead to JavaScript parse error
            # so specify `parse_const_as_str` as True to parse them as string
            detail = local_storage.load_detail(parse_const_as_str=True)
            # ad-hoc step: make logs field empty to avoid too big HTML file
            # we don't provide logs view in visualization page for now
            # when we enable, we will save those big data (e.g. logs) in separate file(s)
            # JS load can be faster than static HTML
            for i in range(len(detail["node_runs"])):
                detail["node_runs"][i]["logs"] = {"stdout": "", "stderr": ""}

            metadata = RunMetadata(
                name=run.name,
                display_name=run.display_name,
                create_time=run.created_on,
                flow_path=run.properties.get(FlowRunProperties.FLOW_PATH, None),
                output_path=run.properties[FlowRunProperties.OUTPUT_PATH],
                tags=run.tags,
                lineage=run.run,
                metrics=local_storage.load_metrics(parse_const_as_str=True),
                dag=local_storage.load_dag_as_string(),
                flow_tools_json=local_storage.load_flow_tools_json(),
                mode=RunMode.EAGER.lower() if local_storage.eager_mode else "",
            )
            details.append(copy.deepcopy(detail))
            metadatas.append(asdict(metadata))
            # TODO: add language to run metadata
            flow_dag = load_yaml_string(metadata.dag) or {}
            configs.append(
                VisualizationConfig(
                    [AvailableIDE.VS_CODE]
                    if flow_dag.get(LANGUAGE_KEY, FlowLanguage.Python) == FlowLanguage.Python
                    else [AvailableIDE.VS]
                )
            )
        data_for_visualize = RunVisualization(
            detail=details,
            metadata=metadatas,
            config=configs,
        )
        html_string = generate_html_string(asdict(data_for_visualize))
        # if html_path is specified, not open it in webbrowser(as it comes from VSC)
        dump_html(html_string, html_path=html_path, open_html=html_path is None)

    def _visualize_with_trace_ui(self, runs: List[Run], html_path: Optional[str] = None) -> None:
        # ensure prompt flow service is running
        pfs_port, service_host = _invoke_pf_svc()
        if not is_pfs_service_healthy(pfs_port, service_host):
            raise PromptFlowServiceInvocationError()
        # concat run names
        runs_query = ",".join([run.name for run in runs])
        trace_ui_url = f"http://{service_host}:{pfs_port}/v1.0/ui/traces/?#run={runs_query}"
        html_string = generate_trace_ui_html_string(trace_ui_url)
        dump_html(html_string, html_path=html_path, open_html=html_path is None)

    def _get_run_flow_type(self, run: Run) -> str:
        # BUG 3195705: observed `Run._flow_type` returns wrong flow type
        # this function is a workaround to get the correct flow type for visualize run scenario
        # so please use this function carefully
        from promptflow._utils.flow_utils import is_prompty_flow, resolve_flow_path

        # prompty: according to the file extension
        if is_prompty_flow(run.flow):
            return FlowType.PROMPTY
        # DAG vs. flex: "entry" in flow.yaml
        # resolve run snapshot, where must exist flow.dag.yaml or flow.flex.yaml
        snapshot_path = run._output_path / LocalStorageFilenames.SNAPSHOT_FOLDER
        flow_directory, yaml_file = resolve_flow_path(snapshot_path)
        yaml_dict = load_yaml(flow_directory / yaml_file)
        if isinstance(yaml_dict, dict) and "entry" in yaml_dict:
            return FlowType.FLEX_FLOW
        else:
            return FlowType.DAG_FLOW

    @monitor_operation(activity_name="pf.runs.visualize", activity_type=ActivityType.PUBLICAPI)
    def visualize(self, runs: Union[str, Run, List[str], List[Run]], **kwargs) -> None:
        """Visualize run(s).

        :param runs: List of run objects, or names of the runs.
        :type runs: Union[str, ~promptflow.sdk.entities.Run, List[str], List[~promptflow.sdk.entities.Run]]
        """
        if not isinstance(runs, list):
            runs = [runs]

        validated_runs: List[Run] = []
        for run in runs:
            run_name = Run._validate_and_return_run_name(run)
            validated_runs.append(self.get(name=run_name))

        html_path = kwargs.pop("html_path", None)

        # if there exists flex flow or prompty run, use trace UI to visualize
        # maybe we can fully switch to trace UI for DAG flow run in the future
        has_flex_or_prompty = False
        for run in validated_runs:
            # for existing run source run, will raise type error when call `_flow_type`, so skip it
            if run._run_source == RunInfoSources.EXISTING_RUN:
                continue
            flow_type = self._get_run_flow_type(run)
            if flow_type == FlowType.FLEX_FLOW or flow_type == FlowType.PROMPTY:
                has_flex_or_prompty = True
                break
        if has_flex_or_prompty is True:
            logger.debug("there exists flex flow or prompty run(s), will use trace UI for visualization.")
            # if `html_path` is specified, which means the call comes from VS Code extension
            # in that case, we should not open browser inside SDK/CLI
            self._visualize_with_trace_ui(runs=validated_runs, html_path=html_path)
        else:
            try:
                self._visualize(validated_runs, html_path=html_path)
            except InvalidRunStatusError as e:
                error_message = f"Cannot visualize non-completed run. {str(e)}"
                logger.error(error_message)

    def _get_outputs(self, run: Union[str, Run]) -> List[Dict[str, Any]]:
        """Get the outputs of the run, load from local storage."""
        local_storage = self._get_local_storage(run)
        return local_storage.load_outputs()

    def _get_inputs(self, run: Union[str, Run]) -> List[Dict[str, Any]]:
        """Get the outputs of the run, load from local storage."""
        local_storage = self._get_local_storage(run)
        return local_storage.load_inputs()

    def _get_outputs_path(self, run: Union[str, Run]) -> str:
        """Get the outputs file path of the run."""
        local_storage = self._get_local_storage(run)
        return local_storage._outputs_path if local_storage.load_outputs() else None

    def _get_data_path(self, run: Union[str, Run]) -> str:
        """Get the outputs file path of the run."""
        local_storage = self._get_local_storage(run)
        # TODO: what if the data is deleted?
        if local_storage._data_path and not os.path.exists(local_storage._data_path):
            raise UserErrorException(
                f"Data path {local_storage._data_path} for run {run.name} does not exist. "
                "Please make sure it exists and not deleted."
            )
        return local_storage._data_path

    def _get_local_storage(self, run: Union[str, Run]) -> LocalStorageOperations:
        """Get the local storage of the run."""
        if isinstance(run, str):
            run = self.get(name=run)
        return LocalStorageOperations(run)

    def _get_telemetry_values(self, *args, **kwargs):
        activity_name = kwargs.get("activity_name", None)
        telemetry_values = super()._get_telemetry_values(*args, **kwargs)
        try:
            if activity_name == "pf.runs.create_or_update":
                run: Run = kwargs.get("run", None) or args[0]
                telemetry_values["flow_type"] = run._flow_type
        except Exception as e:
            logger.error(f"Failed to get telemetry values: {str(e)}")

        return telemetry_values
