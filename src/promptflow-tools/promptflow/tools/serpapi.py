import json
import sys
from enum import Enum

import requests
# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import ToolProvider, tool
from promptflow.connections import SerpConnection
from promptflow.exceptions import PromptflowException
from promptflow.tools.exception import SerpAPIUserError, SerpAPISystemError


class SafeMode(str, Enum):
    ACTIVE = "active"
    OFF = "off"


class Engine(str, Enum):
    GOOGLE = "google"
    BING = "bing"


class SerpAPI(ToolProvider):
    def __init__(self, connection: SerpConnection):
        super().__init__()
        self.connection = connection

    def extract_error_message_from_json(self, error_data):
        error_message = ""
        # For request was rejected. For example, the api_key is not valid
        if "error" in error_data:
            error_message = error_data["error"]

        return str(error_message)

    def safe_extract_error_message(self, response):
        default_error_message = f"SerpAPI search request failed: {response.text}"
        try:
            # Keep the same style as SerpAPIClient
            error_data = json.loads(response.text)
            print(f"Response text json: {json.dumps(error_data)}", file=sys.stderr)
            error_message = self.extract_error_message_from_json(error_data)
            error_message = error_message if len(error_message) > 0 else default_error_message
            return error_message

        except Exception as e:
            # Swallow any exception when extract detailed error message
            print(
                f"Unexpected exception occurs while extract error message "
                f"from response: {type(e).__name__}: {str(e)}",
                file=sys.stderr,
            )
            return default_error_message

    # flake8: noqa: C901
    @tool
    def search(
            self,
            query: str,  # this is required
            location: str = None,
            safe: SafeMode = SafeMode.OFF,  # Not default to be SafeMode.OFF
            num: int = 10,
            engine: Engine = Engine.GOOGLE,  # this is required
    ):
        from serpapi import SerpApiClient

        # required parameters. https://serpapi.com/search-api.
        params = {
            "q": query,
            "location": location,
            "api_key": self.connection.api_key,
        }
        if isinstance(engine, Engine):
            params["engine"] = engine.value
        else:
            params["engine"] = engine

        if safe == SafeMode.ACTIVE:
            # Ingore invalid value and safe="off" (as default)
            # For bing and google, they use diff parameters
            if params["engine"].lower() == "google":
                params["safe"] = "Active"
            else:
                params["safeSearch"] = "Strict"

        if int(num) > 0:
            # to combine multiple engines together, we use "num" as the parameter for such purpose
            if params["engine"].lower() == "google":
                params["num"] = int(num)
            else:
                params["count"] = int(num)

        search = SerpApiClient(params)

        # get response
        try:
            response = search.get_response()
            if response.status_code == requests.codes.ok:
                # default output is json
                return json.loads(response.text)
            else:
                # Step I: Try to get accurate error message at best
                error_message = self.safe_extract_error_message(response)

                # Step II: Construct PromptflowException
                if response.status_code >= 500:
                    raise SerpAPISystemError(message=error_message)
                else:
                    raise SerpAPIUserError(message=error_message)
        except Exception as e:
            # SerpApi is super robust. Set basic error handle
            if not isinstance(e, PromptflowException):
                print(f"Unexpected exception occurs: {type(e).__name__}: {str(e)}", file=sys.stderr)
                error_message = f"SerpAPI search request failed: {type(e).__name__}: {str(e)}"
                raise SerpAPISystemError(message=error_message)
            raise


@tool
def search(
        connection: SerpConnection,
        query: str,  # this is required
        location: str = None,
        safe: SafeMode = SafeMode.OFF,  # Not default to be SafeMode.OFF
        num: int = 10,
        engine: Engine = Engine.GOOGLE,  # this is required
):
    return SerpAPI(connection).search(
        query=query,
        location=location,
        safe=safe,
        num=num,
        engine=engine,
    )
