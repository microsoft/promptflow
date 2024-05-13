# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import copy
import shutil
from os import PathLike
from pathlib import Path
from typing import List, Optional, Union

from promptflow._sdk._constants import MAX_LIST_CLI_RESULTS, ExperimentStatus, ListViewType
from promptflow._sdk._errors import ExperimentExistsError, RunOperationError
from promptflow._sdk._orm.experiment import Experiment as ORMExperiment
from promptflow._sdk._telemetry import ActivityType, TelemetryMixin, monitor_operation
from promptflow._sdk._utilities.general_utils import json_load, safe_parse_object_list
from promptflow._sdk.entities._experiment import Experiment
from promptflow._utils.logger_utils import get_cli_sdk_logger

logger = get_cli_sdk_logger()


class ExperimentOperations(TelemetryMixin):
    """ExperimentOperations."""

    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self._client = client

    @monitor_operation(activity_name="pf.experiment.list", activity_type=ActivityType.PUBLICAPI)
    def list(
        self,
        max_results: Optional[int] = MAX_LIST_CLI_RESULTS,
        *,
        list_view_type: ListViewType = ListViewType.ACTIVE_ONLY,
    ) -> List[Experiment]:
        """List experiments.

        :param max_results: Max number of results to return. Default: 50.
        :type max_results: Optional[int]
        :param list_view_type: View type for including/excluding (for example) archived experiments.
            Default: ACTIVE_ONLY.
        :type list_view_type: Optional[ListViewType]
        :return: List of experiment objects.
        :rtype: List[~promptflow.entities.Experiment]
        """
        orm_experiments = ORMExperiment.list(max_results=max_results, list_view_type=list_view_type)
        return safe_parse_object_list(
            obj_list=orm_experiments,
            parser=Experiment._from_orm_object,
            message_generator=lambda x: f"Error parsing experiment {x.name!r}, skipped.",
        )

    @monitor_operation(activity_name="pf.experiment.get", activity_type=ActivityType.PUBLICAPI)
    def get(self, name: str) -> Experiment:
        """Get an experiment entity.

        :param name: Name of the experiment.
        :type name: str
        :return: experiment object retrieved from the database.
        :rtype: ~promptflow.entities.Experiment
        """
        from promptflow._sdk._orchestrator.experiment_orchestrator import ExperimentOrchestrator

        ExperimentOrchestrator.get_status(name)
        return Experiment._from_orm_object(ORMExperiment.get(name))

    @monitor_operation(activity_name="pf.experiment.create_or_update", activity_type=ActivityType.PUBLICAPI)
    def create_or_update(self, experiment: Experiment, **kwargs) -> Experiment:
        """Create or update an experiment.

        :param experiment: Experiment object to create or update.
        :type experiment: ~promptflow.entities.Experiment
        :return: Experiment object created or updated.
        :rtype: ~promptflow.entities.Experiment
        """
        orm_experiment = experiment._to_orm_object()
        try:
            orm_experiment.dump()
            return self.get(experiment.name)
        except ExperimentExistsError:
            logger.info(f"Experiment {experiment.name!r} already exists, updating.")
            existing_experiment = orm_experiment.get(experiment.name)
            existing_experiment.update(
                status=orm_experiment.status,
                description=orm_experiment.description,
                last_start_time=orm_experiment.last_start_time,
                last_end_time=orm_experiment.last_end_time,
                node_runs=orm_experiment.node_runs,
                inputs=orm_experiment.inputs,
                data=orm_experiment.data,
            )
            return self.get(experiment.name)

    @monitor_operation(activity_name="pf.experiment.start", activity_type=ActivityType.PUBLICAPI)
    def start(self, experiment: Experiment, stream=False, inputs=None, **kwargs) -> Experiment:
        """
        Start an experiment.

        :param experiment: Experiment object.
        :type experiment: ~promptflow.entities.Experiment
        :param stream: Indicates whether to stream the experiment execution logs to the console.
        :type stream: bool
        :param inputs: Input dict to override.
        :type inputs: Dict[str, str]
        :return: Experiment object started.
        :rtype: ~promptflow.entities.Experiment
        """
        from promptflow._sdk._orchestrator.experiment_orchestrator import ExperimentOrchestrator

        if experiment._source_path:
            # Update snapshot for anonymous experiment
            logger.debug("Start saving snapshot and update node.")
            snapshots = experiment._output_dir / "snapshots"
            if snapshots.exists():
                shutil.rmtree(snapshots)
            experiment._save_snapshot_and_update_node()

        # Update experiment inputs
        experiment = copy.deepcopy(experiment)
        inputs = inputs or {}
        for name, value in inputs.items():
            exp_input = next(filter(lambda exp_input: exp_input.name == name, experiment.inputs), None)
            if exp_input:
                exp_input.default = value
                continue
            exp_data = next(filter(lambda exp_data: exp_data.name == name, experiment.data), None)
            if exp_data:
                exp_data.path = Path(value).absolute().as_posix()
                continue
            logger.warning(f"Input {name} doesn't exist in experiment.")
        experiment = self.create_or_update(experiment)

        if experiment.status in [ExperimentStatus.QUEUING, ExperimentStatus.IN_PROGRESS]:
            raise RunOperationError(
                f"Experiment {experiment.name} is {experiment.status}, cannot be started repeatedly."
            )
        if stream:
            return ExperimentOrchestrator(self._client, experiment).start(**kwargs)
        else:
            return ExperimentOrchestrator(self._client, experiment).async_start(**kwargs)

    @monitor_operation(activity_name="pf.experiment.stop", activity_type=ActivityType.PUBLICAPI)
    def stop(self, experiment: Experiment, **kwargs) -> Experiment:
        """Stop an experiment.

        :param experiment: Experiment name.
        :type experiment: ~promptflow.entities.Experiment
        :return: Experiment object started.
        :rtype: ~promptflow.entities.Experiment
        """
        from promptflow._sdk._orchestrator.experiment_orchestrator import ExperimentOrchestrator

        ExperimentOrchestrator(self._client, experiment).stop()
        return self.get(experiment.name)

    @monitor_operation(activity_name="pf.experiment.test", activity_type=ActivityType.PUBLICAPI)
    def test(self, experiment: Union[Path, str], inputs=None, **kwargs) -> Experiment:
        """Test an experiment.

        :param experiment: Experiment yaml file path.
        :type experiment: Union[Path, str]
        :param inputs: Input parameters for flow.
        :type inputs: dict
        """
        from promptflow._sdk._orchestrator.experiment_orchestrator import ExperimentOrchestrator

        from .._load_functions import _load_experiment_template

        experiment_template = _load_experiment_template(experiment)
        output_path = kwargs.pop("output_path", None)
        session = kwargs.pop("session", None)
        return ExperimentOrchestrator(client=self._client, experiment=None).test(
            experiment_template,
            inputs=inputs,
            output_path=output_path,
            session=session,
            **kwargs,
        )

    def _test_with_ui(
        self, experiment: Experiment, output_path: PathLike, environment_variables=None, **kwargs
    ) -> Experiment:
        """Test an experiment by http request.

        :param experiment: Experiment yaml file path.
        :type experiment: Union[Path, str]
        :param environment_variables: Environment variables for experiment.
        :type environment_variables: dict
        """
        # The api is used for ux calling pfs. We need the api to read detail.json and log and return to ux as the
        # format they expected.
        result = self._test_flow(
            experiment=experiment, environment_variables=environment_variables, output_path=output_path, **kwargs
        )
        return_output = {}
        for key in result:
            detail_path = output_path / key / "flow.detail.json"
            log_path = output_path / key / "flow.log"
            detail_content = json_load(detail_path)
            with open(log_path, "r") as file:
                log_content = file.read()
            return_output[key] = {
                "detail": detail_content,
                "log": log_content,
                "output_path": str(output_path / key),
            }
        return return_output

    @monitor_operation(activity_name="pf.experiment._test_flow", activity_type=ActivityType.INTERNALCALL)
    def _test_flow(
        self,
        experiment: Union[Path, str],
        flow: Union[Path, str] = None,
        inputs=None,
        environment_variables=None,
        **kwargs,
    ):
        """Test flow in experiment.

        :param flow: Flow dag yaml file path, will resolve the first flow if None passed in.
        :type flow: Union[Path, str]
        :param experiment: Experiment yaml file path.
        :type experiment: Union[Path, str]
        :param inputs: Input parameters for flow.
        :type inputs: dict
        :param environment_variables: Environment variables for flow.
        :type environment_variables: dict
        """
        from promptflow._sdk._orchestrator.experiment_orchestrator import ExperimentOrchestrator

        from .._load_functions import _load_experiment_template

        experiment_template = _load_experiment_template(experiment)
        output_path = kwargs.get("output_path", None)
        session = kwargs.get("session", None)
        context = kwargs.get("context", None)
        return ExperimentOrchestrator(client=self._client, experiment=None).test_flow(
            experiment_template,
            flow,
            inputs,
            environment_variables,
            output_path=output_path,
            session=session,
            context=context,
        )
