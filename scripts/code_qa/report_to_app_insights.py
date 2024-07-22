from typing import Dict, Optional, Union

import argparse
import json
import platform

from promptflow._sdk._configuration import Configuration
from promptflow._sdk._telemetry.telemetry import get_telemetry_logger
from xml.dom import minidom


def parse_junit_xml(fle: str) -> Dict[str, Dict[str, Union[float, str]]]:
    """
    Parse the xml in Junit xml format.

    :param fle: The file in JUnit xml format.
    :type fle: str
    :return: The dictionary with tests, their run times and pass/fail status.
    """
    test_results = {}
    dom = minidom.parse(fle)
    # Take node list Document/testsuites/testsuite/
    for test in dom.firstChild.firstChild.childNodes:
        test_name = f"{test.attributes['classname'].value}::{test.attributes['name'].value}"
        test_results[test_name] = {'fail_message': '', 'time': float(test.attributes['time'].value)}

        for child in test.childNodes:
            if child.nodeName == 'failure':
                test_results[test_name]['fail_message'] = child.attributes["message"].value
    return test_results


def main(activity_name: str,
         value: Union[float, str],
         run_id: str,
         workflow: str,
         action: str,
         branch: str,
         junit_file: Optional[str]) -> None:
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
    :type action: str
    :param branch: The branch from which the CI-CD was triggered.
    :type branch: str
    :param junit_file: The path to junit test file results.
    :type junit_file: str
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
        "branch": branch,
        "git_hub_action_run_id": run_id,
        "git_hub_workflow": workflow
    }
    if junit_file:
        junit_dict = parse_junit_xml(junit_file)
        for k, v in junit_dict.items():
            if v["fail_message"]:
                # Do not log time together with fail message.
                continue
            activity_info[k] = v['time']
    else:
        if isinstance(value, str):
            activity_info.update(json.loads(value))
        else:
            activity_info["value"] = value

    # write information to the application insights.
    logger.info(action, extra={"custom_dimensions": activity_info})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Log the value to application insights along with platform characteristics and run ID.")
    parser.add_argument('--activity', help='The activity to be logged.',
                        required=True)
    parser.add_argument(
        '--value',
        help='The floating point value for activity or a set of values in key-value format.',
        required=False,
        default=-1)
    parser.add_argument('--junit-xml', help='The path to junit-xml file.',
                        dest="junit_xml", required=False, default=None)
    parser.add_argument('--git-hub-action-run-id', dest='run_id',
                        help='The run ID of GitHub action run.', required=True)
    parser.add_argument('--git-hub-workflow', dest='workflow',
                        help='The name of a workflow or a path to workflow file.', required=True)
    parser.add_argument('--git-hub-action', dest='action',
                        help='Git hub action or step.', required=True)
    parser.add_argument('--git-branch', dest='branch',
                        help='Git hub Branch.', required=True)
    args = parser.parse_args()
    main(args.activity, args.value, args.run_id, args.workflow, args.action, args.branch, args.junit_xml)
