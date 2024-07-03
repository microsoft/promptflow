import argparse
import platform

from promptflow._sdk._configuration import Configuration
from promptflow._sdk._telemetry.telemetry import get_telemetry_logger


def main(activity_name: str, value: float, run_id: str, workflow: str, action: str) -> None:
    """
    Log the CI-CD event.

    :param activity_name: The name of a n activity to be logged, for example, installation time.
    :type activity_name: str
    :param value: The value of a parameter
    :type value: float
    :param run_id: The CI-CD run id.
    :type run_id: str
    :param workflow: The name of a workflow or path to a workflow file.
    :type workflow: str
    :param action: The name of running action or a step.
    :type acion: str
    """
    # Enable telemetry
    config = Configuration.get_instance()
    config.set_config(Configuration.COLLECT_TELEMETRY, True)
    logger = get_telemetry_logger()
    activity_info = {
        "activity_name": activity_name,
        "activity_type": "ci_cd_analytics",
        "OS": platform.system(),
        "OS_release": platform.release(),
        "value": value,
        "git_hub_action_run_id": run_id,
        "git_hub_workflow": workflow
    }
    # write information to the application insights.
    logger.info(action, extra={"custom_dimensions": activity_info})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Log the value to application insights along with platform characteristics and run ID.")
    parser.add_argument('--activity', type=ascii, help='The activity to be logged.',
                        required=True)
    parser.add_argument('--value', type=float, help='The value for activity.',
                        required=True)
    parser.add_argument('--git-hub-action-run-id', type=ascii, dest='run_id',
                        help='The run ID of GitHub action run.', required=True)
    parser.add_argument('--git-hub-workflow', type=ascii, dest='workflow',
                        help='The name of a workflow or a path to workflow file.', required=True)
    parser.add_argument('--git-hub-action', type=ascii, dest='action',
                        help='Git hub action or step.', required=True)
    args = parser.parse_args()
    main(args.activity, args.value, args.run_id, args.workflow, args.action)
