# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import List, Optional

from promptflow._sdk._constants import MAX_LIST_CLI_RESULTS, ListViewType
from promptflow._sdk._errors import ExperimentExistsError, ExperimentNotFoundError, ExperimentValueError
from promptflow._sdk._orm.experiment import Experiment as ORMExperiment
from promptflow._sdk._telemetry import ActivityType, TelemetryMixin, monitor_operation
from promptflow._sdk._utils import safe_parse_object_list
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
        try:
            return Experiment._from_orm_object(ORMExperiment.get(name))
        except ExperimentNotFoundError as e:
            raise e

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
            )
            return self.get(experiment.name)

    @monitor_operation(activity_name="pf.experiment.start", activity_type=ActivityType.PUBLICAPI)
    def start(self, name: str, **kwargs) -> Experiment:
        """Start an experiment.

        :param name: Experiment name.
        :type name: str
        :return: Experiment object started.
        :rtype: ~promptflow.entities.Experiment
        """
        from promptflow._sdk._submitter.experiment_orchestrator import ExperimentOrchestrator

        if not isinstance(name, str):
            raise ExperimentValueError(f"Invalid type {type(name)} for name. Must be str.")
        return ExperimentOrchestrator(self._client.runs, self).start(self.get(name), **kwargs)
