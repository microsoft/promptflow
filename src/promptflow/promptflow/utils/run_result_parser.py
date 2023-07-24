from promptflow.exceptions import ErrorResponse
from promptflow.runtime.error_codes import RunResultParseError
from promptflow.runtime.utils import logger


class RunResultParser:
    """This class parses the run result response.

    It is able to extract some specific information from the result.
    """

    def __init__(self, result: dict):
        self._result = result

    def get_error_response(self):
        """Get the error response from the run result.

        This method should never fail.
        If errors occur in the extraction process, it will be logged and
        wrapped as a `RunResultParseError`.
        """
        try:
            error = self._extract_error_from_run_result()
            if error:
                return ErrorResponse.from_error_dict(error).to_dict()
            else:
                return None
        except Exception as e:
            # Don't raise if errors happen when extracting error from result
            # Instead, log the error and put the error into errorResponse
            try:
                logger.warning("Hit exception when extracting error from result: %s", e)
                parse_error = RunResultParseError(error=e)
                return ErrorResponse.from_exception(parse_error).to_dict()
            except Exception as e1:
                logger.warning("Hit exception when creating error response: %s", e1)
                return None

    def _get_first_error_from_run_list(self, runs):
        """Given a list of run info, get the first error message in the list."""
        if not runs:
            return None
        for run in runs:
            error = run.get("error")
            if error:
                return error
        return None

    def _extract_error_from_run_result(self):
        """Return the error for the root run if any.

        This method may raise values that are not PromptflowException.
        It is by design, will be wrapped into a `RunResultParseError`
        and then wrapped as an ErrorResponse.
        """
        if self._result is None:
            raise ValueError("Run result is None.")

        flow_runs = self._result.get("flow_runs")
        if not flow_runs:
            # If there's no `flow_runs` in the result, it should be a NodeRun.
            # For this mode, we extract the first error inside `node_runs`.
            #
            # TODO: It is better to check run_mode here instead of guessing.
            #       We plan to generate the error response inside the executor
            #       instead of checking them inside the runtime layer here.
            # See https://msdata.visualstudio.com/Vienna/_workitems/edit/2423172
            node_runs = self._result.get("node_runs")
            if not node_runs:
                raise ValueError("Neither flow runs or node runs is found in the run result.")

            return self._get_first_error_from_run_list(node_runs)

        run_to_look_into = flow_runs[0]

        # Usually, the flow_runs[1] contains more meaningful error message.
        # We use flow_runs[1] instead of the root run when possible.
        # In addition, when there are variant runs, there might be flow_runs[2], 3, or others.
        # For now, we don't look into them for simplicity.
        if len(flow_runs) > 1:
            run_to_look_into = flow_runs[1]

        return run_to_look_into.get("error")
