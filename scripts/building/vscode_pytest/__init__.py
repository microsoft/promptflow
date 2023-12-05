# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# Copy and modified from vscode source code.

import json
import os
import pathlib
import traceback
from typing import Any, Dict, List, Optional, Union
from typing_extensions import Literal, TypedDict

import pytest


class TestData(TypedDict):
    """A general class that all test objects inherit from."""

    name: str
    path: pathlib.Path
    type_: Literal["class", "function", "file", "folder", "test", "error"]
    id_: str


class TestItem(TestData):
    """A class defining test items."""

    lineno: str
    runID: str


class TestNode(TestData):
    """A general class that handles all test data which contains children."""

    children: "list[Union[TestNode, TestItem, None]]"


class VSCodePytestError(Exception):
    """A custom exception class for pytest errors."""

    def __init__(self, message):
        super().__init__(message)


ERRORS = []


def pytest_exception_interact(node, call, report):
    """A pytest hook that is called when an exception is raised which could be handled.

    Keyword arguments:
    node -- the node that raised the exception.
    call -- the call object.
    report -- the report object of either type CollectReport or TestReport.
    """
    # call.excinfo is the captured exception of the call, if it raised as type ExceptionInfo.
    # call.excinfo.exconly() returns the exception as a string.
    # See if it is during discovery or execution.
    # if discovery, then add the error to error logs.
    if isinstance(report, pytest.CollectReport):
        if call.excinfo and call.excinfo.typename != "AssertionError":
            if report.outcome == "skipped" and "SkipTest" in str(call):
                return
            ERRORS.append(
                call.excinfo.exconly() + "\n Check Python Test Logs for more details."
            )
        else:
            ERRORS.append(
                report.longreprtext + "\n Check Python Test Logs for more details."
            )
    else:
        # if execution, send this data that the given node failed.
        report_value = "error"
        if call.excinfo.typename == "AssertionError":
            report_value = "failure"
        node_id = str(node.nodeid)
        if node_id not in collected_tests_so_far:
            collected_tests_so_far.append(node_id)
            item_result = create_test_outcome(
                node_id,
                report_value,
                "Test failed with exception",
                report.longreprtext,
            )
            collected_test = testRunResultDict()
            collected_test[node_id] = item_result


def pytest_keyboard_interrupt(excinfo):
    """A pytest hook that is called when a keyboard interrupt is raised.

    Keyword arguments:
    excinfo -- the exception information of type ExceptionInfo.
    """
    # The function execonly() returns the exception as a string.
    ERRORS.append(excinfo.exconly() + "\n Check Python Test Logs for more details.")


class TestOutcome(Dict):
    """A class that handles outcome for a single test.

    for pytest the outcome for a test is only 'passed', 'skipped' or 'failed'
    """

    test: str
    outcome: Literal["success", "failure", "skipped", "error"]
    message: Union[str, None]
    traceback: Union[str, None]
    subtest: Optional[str]


def create_test_outcome(
    test: str,
    outcome: str,
    message: Union[str, None],
    traceback: Union[str, None],
    subtype: Optional[str] = None,
) -> TestOutcome:
    """A function that creates a TestOutcome object."""
    return TestOutcome(
        test=test,
        outcome=outcome,
        message=message,
        traceback=traceback,  # TODO: traceback
        subtest=None,
    )


class testRunResultDict(Dict[str, Dict[str, TestOutcome]]):
    """A class that stores all test run results."""

    outcome: str
    tests: Dict[str, TestOutcome]


IS_DISCOVERY = False


def pytest_load_initial_conftests(early_config, parser, args):
    if "--collect-only" in args:
        global IS_DISCOVERY
        IS_DISCOVERY = True


collected_tests_so_far = list()


ERROR_MESSAGE_CONST = {
    2: "Pytest was unable to start or run any tests due to issues with test discovery or test collection.",
    3: "Pytest was interrupted by the user, for example by pressing Ctrl+C during test execution.",
    4: "Pytest encountered an internal error or exception during test execution.",
    5: "Pytest was unable to find any tests to run.",
}


def check_skipped_wrapper(item):
    """A function that checks if a test is skipped or not by check its markers and its parent markers.

    Returns True if the test is marked as skipped at any level, False otherwise.

    Keyword arguments:
    item -- the pytest item object.
    """
    if item.own_markers:
        if check_skipped_condition(item):
            return True
    parent = item.parent
    while isinstance(parent, pytest.Class):
        if parent.own_markers:
            if check_skipped_condition(parent):
                return True
        parent = parent.parent
    return False


def check_skipped_condition(item):
    """A helper function that checks if a item has a skip or a true skip condition.

    Keyword arguments:
    item -- the pytest item object.
    """

    for marker in item.own_markers:
        # If the test is marked with skip then it will not hit the pytest_report_teststatus hook,
        # therefore we need to handle it as skipped here.
        skip_condition = False
        if marker.name == "skipif":
            skip_condition = any(marker.args)
        if marker.name == "skip" or skip_condition:
            return True
    return False


def pytest_sessionfinish(session, exitstatus):
    """A pytest hook that is called after pytest has fulled finished.

    Keyword arguments:
    session -- the pytest session object.
    exitstatus -- the status code of the session.

    0: All tests passed successfully.
    1: One or more tests failed.
    2: Pytest was unable to start or run any tests due to issues with test discovery or test collection.
    3: Pytest was interrupted by the user, for example by pressing Ctrl+C during test execution.
    4: Pytest encountered an internal error or exception during test execution.
    5: Pytest was unable to find any tests to run.
    """
    print(
        "pytest session has finished, exit status: ",
        exitstatus,
        "in discovery? ",
        IS_DISCOVERY,
    )
    if IS_DISCOVERY:
        if not (exitstatus == 0 or exitstatus == 1 or exitstatus == 5):
            pass
        try:
            session_node: Union[TestNode, None] = build_test_tree(session)
            if not session_node:
                raise VSCodePytestError(
                    "Something went wrong following pytest finish, \
                        no session node was created"
                )
        except Exception as e:
            ERRORS.append(
                f"Error Occurred, traceback: {(traceback.format_exc() if e.__traceback__ else '')}"
            )
    else:
        if exitstatus == 0 or exitstatus == 1:
            pass
        else:
            ERRORS.append(
                f"Pytest exited with error status: {exitstatus}, {ERROR_MESSAGE_CONST[exitstatus]}"
            )


def build_test_tree(session: pytest.Session) -> TestNode:
    """Builds a tree made up of testing nodes from the pytest session.

    Keyword arguments:
    session -- the pytest session object.
    """
    session_node = create_session_node(session)
    session_children_dict: Dict[str, TestNode] = {}
    file_nodes_dict: Dict[Any, TestNode] = {}
    class_nodes_dict: Dict[str, TestNode] = {}
    function_nodes_dict: Dict[str, TestNode] = {}

    for test_case in session.items:
        test_node = create_test_node(test_case)
        if isinstance(test_case.parent, pytest.Class):
            try:
                test_class_node = class_nodes_dict[test_case.parent.nodeid]
            except KeyError:
                test_class_node = create_class_node(test_case.parent)
                class_nodes_dict[test_case.parent.nodeid] = test_class_node
            test_class_node["children"].append(test_node)
            if test_case.parent.parent:
                parent_module = test_case.parent.parent
            else:
                ERRORS.append(f"Test class {test_case.parent} has no parent")
                break
            # Create a file node that has the class as a child.
            try:
                test_file_node: TestNode = file_nodes_dict[parent_module]
            except KeyError:
                test_file_node = create_file_node(parent_module)
                file_nodes_dict[parent_module] = test_file_node
            # Check if the class is already a child of the file node.
            if test_class_node not in test_file_node["children"]:
                test_file_node["children"].append(test_class_node)
        elif hasattr(test_case, "callspec"):  # This means it is a parameterized test.
            function_name: str = ""
            # parameterized test cases cut the repetitive part of the name off.
            name_split = test_node["name"].split("[")
            test_node["name"] = "[" + name_split[1]
            parent_path = os.fspath(get_node_path(test_case)) + "::" + name_split[0]
            try:
                function_name = test_case.originalname  # type: ignore
                function_test_case = function_nodes_dict[parent_path]
            except AttributeError:  # actual error has occurred
                ERRORS.append(
                    f"unable to find original name for {test_case.name} with parameterization detected."
                )
                raise VSCodePytestError(
                    "Unable to find original name for parameterized test case"
                )
            except KeyError:
                function_test_case: TestNode = create_parameterized_function_node(
                    function_name, get_node_path(test_case), test_case.nodeid
                )
                function_nodes_dict[parent_path] = function_test_case
            function_test_case["children"].append(test_node)
            # Now, add the function node to file node.
            try:
                parent_test_case = file_nodes_dict[test_case.parent]
            except KeyError:
                parent_test_case = create_file_node(test_case.parent)
                file_nodes_dict[test_case.parent] = parent_test_case
            if function_test_case not in parent_test_case["children"]:
                parent_test_case["children"].append(function_test_case)
        else:  # This includes test cases that are pytest functions or a doctests.
            try:
                parent_test_case = file_nodes_dict[test_case.parent]
            except KeyError:
                parent_test_case = create_file_node(test_case.parent)
                file_nodes_dict[test_case.parent] = parent_test_case
            parent_test_case["children"].append(test_node)
    created_files_folders_dict: Dict[str, TestNode] = {}
    for _, file_node in file_nodes_dict.items():
        # Iterate through all the files that exist and construct them into nested folders.
        root_folder_node: TestNode = build_nested_folders(
            file_node, created_files_folders_dict, session
        )
        # The final folder we get to is the highest folder in the path
        # and therefore we add this as a child to the session.
        root_id = root_folder_node.get("id_")
        if root_id and root_id not in session_children_dict:
            session_children_dict[root_id] = root_folder_node
    session_node["children"] = list(session_children_dict.values())
    return session_node


def build_nested_folders(
    file_node: TestNode,
    created_files_folders_dict: Dict[str, TestNode],
    session: pytest.Session,
) -> TestNode:
    """Takes a file or folder and builds the nested folder structure for it.

    Keyword arguments:
    file_module -- the created module for the file we  are nesting.
    file_node -- the file node that we are building the nested folders for.
    created_files_folders_dict -- Dictionary of all the folders and files that have been created.
    session -- the pytest session object.
    """
    prev_folder_node = file_node

    # Begin the iterator_path one level above the current file.
    iterator_path = file_node["path"].parent
    while iterator_path != get_node_path(session):
        curr_folder_name = iterator_path.name
        try:
            curr_folder_node: TestNode = created_files_folders_dict[
                os.fspath(iterator_path)
            ]
        except KeyError:
            curr_folder_node: TestNode = create_folder_node(
                curr_folder_name, iterator_path
            )
            created_files_folders_dict[os.fspath(iterator_path)] = curr_folder_node
        if prev_folder_node not in curr_folder_node["children"]:
            curr_folder_node["children"].append(prev_folder_node)
        iterator_path = iterator_path.parent
        prev_folder_node = curr_folder_node
    return prev_folder_node


def create_test_node(
    test_case: pytest.Item,
) -> TestItem:
    """Creates a test node from a pytest test case.

    Keyword arguments:
    test_case -- the pytest test case.
    """
    test_case_loc: str = (
        str(test_case.location[1] + 1) if (test_case.location[1] is not None) else ""
    )
    return {
        "name": test_case.name,
        "path": get_node_path(test_case),
        "lineno": test_case_loc,
        "type_": "test",
        "id_": test_case.nodeid,
        "runID": test_case.nodeid,
    }


def create_session_node(session: pytest.Session) -> TestNode:
    """Creates a session node from a pytest session.

    Keyword arguments:
    session -- the pytest session.
    """
    node_path = get_node_path(session)
    return {
        "name": session.name,
        "path": node_path,
        "type_": "folder",
        "children": [],
        "id_": os.fspath(node_path),
    }


def create_class_node(class_module: pytest.Class) -> TestNode:
    """Creates a class node from a pytest class object.

    Keyword arguments:
    class_module -- the pytest object representing a class module.
    """
    return {
        "name": class_module.name,
        "path": get_node_path(class_module),
        "type_": "class",
        "children": [],
        "id_": class_module.nodeid,
    }


def create_parameterized_function_node(
    function_name: str, test_path: pathlib.Path, test_id: str
) -> TestNode:
    """Creates a function node to be the parent for the parameterized test nodes.

    Keyword arguments:
    function_name -- the name of the function.
    test_path -- the path to the test file.
    test_id -- the id of the test, which is a parameterized test so it
      must be edited to get a unique id for the function node.
    """
    function_id: str = test_id.split("::")[0] + "::" + function_name
    return {
        "name": function_name,
        "path": test_path,
        "type_": "function",
        "children": [],
        "id_": function_id,
    }


def create_file_node(file_module: Any) -> TestNode:
    """Creates a file node from a pytest file module.

    Keyword arguments:
    file_module -- the pytest file module.
    """
    node_path = get_node_path(file_module)
    return {
        "name": node_path.name,
        "path": node_path,
        "type_": "file",
        "id_": os.fspath(node_path),
        "children": [],
    }


def create_folder_node(folder_name: str, path_iterator: pathlib.Path) -> TestNode:
    """Creates a folder node from a pytest folder name and its path.

    Keyword arguments:
    folderName -- the name of the folder.
    path_iterator -- the path of the folder.
    """
    return {
        "name": folder_name,
        "path": path_iterator,
        "type_": "folder",
        "id_": os.fspath(path_iterator),
        "children": [],
    }


class DiscoveryPayloadDict(TypedDict):
    """A dictionary that is used to send a post request to the server."""

    cwd: str
    status: Literal["success", "error"]
    tests: Optional[TestNode]
    error: Optional[List[str]]


class ExecutionPayloadDict(Dict):
    """
    A dictionary that is used to send a execution post request to the server.
    """

    cwd: str
    status: Literal["success", "error"]
    result: Union[testRunResultDict, None]
    not_found: Union[List[str], None]  # Currently unused need to check
    error: Union[str, None]  # Currently unused need to check


def get_node_path(node: Any) -> pathlib.Path:
    return getattr(node, "path", pathlib.Path(node.fspath))


class PathEncoder(json.JSONEncoder):
    """A custom JSON encoder that encodes pathlib.Path objects as strings."""

    def default(self, obj):
        if isinstance(obj, pathlib.Path):
            return os.fspath(obj)
        return super().default(obj)
