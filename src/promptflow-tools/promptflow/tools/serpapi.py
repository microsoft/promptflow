import json
import sys
from enum import Enum

import requests

from promptflow.core.tool import ToolProvider, tool
from promptflow.connections import SerpConnection
from promptflow.core.tools_manager import register_builtin_method, register_builtins
from promptflow.exceptions import PromptflowException
from promptflow.tools.common import to_bool
from promptflow.tools.exception import SerpAPIUserError, SerpAPISystemError
from promptflow.utils.utils import deprecated


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

    @staticmethod
    @deprecated(replace="SerpAPI()")
    def from_config(config: SerpConnection):
        return SerpAPI(config)

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
            google_domain: str = "google.com",
            gl: str = None,
            hl: str = None,
            lr: str = None,
            tbs: str = None,
            safe: SafeMode = SafeMode.OFF,  # Not default to be SafeMode.OFF
            nfpr: bool = False,
            filter: str = None,
            tbm: str = None,
            start: int = 0,
            num: int = 10,
            ijn: int = 0,
            engine: Engine = Engine.GOOGLE,  # this is required
            device: str = "desktop",
            no_cache: bool = False,
            asynch: bool = False,
            output: str = "JSON",
    ):
        from serpapi import SerpApiClient

        # required parameters. https://serpapi.com/search-api.
        params = {
            "q": query,
            "location": location,
            "google_domain": google_domain,
            "gl": gl,
            "hl": hl,
            "lr": lr,
            "tbs": tbs,
            "filter": filter,
            "tbm": tbm,
            "device": device,
            "no_cache": to_bool(no_cache),
            "async": to_bool(asynch),
            "api_key": self.connection.api_key,
            "output": output,
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

        if to_bool(nfpr):
            params["nfpr"] = True
        if int(start) > 0:
            params["start"] = int(start)
        if int(num) > 0:
            # to combine multiple engines togather, we use "num" as the parameter for such purpose
            if params["engine"].lower() == "google":
                params["num"] = int(num)
            else:
                params["count"] = int(num)
        if int(ijn) > 0:
            params["ijn"] = int(ijn)

        search = SerpApiClient(params)

        # get response
        try:
            response = search.get_response()
            if response.status_code == requests.codes.ok:
                if output.lower() == "json":
                    # Keep the same as SerpAPIClient.get_json()
                    return json.loads(response.text)
                else:
                    # Keep the same as SerpAPIClient.get_html()
                    return response.text
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


register_builtins(SerpAPI)


@tool
def search(
        connection: SerpConnection,
        query: str,  # this is required
        location: str = None,
        google_domain: str = "google.com",
        gl: str = None,
        hl: str = None,
        lr: str = None,
        tbs: str = None,
        safe: SafeMode = SafeMode.OFF,  # Not default to be SafeMode.OFF
        nfpr: bool = False,
        filter: str = None,
        tbm: str = None,
        start: int = 0,
        num: int = 10,
        ijn: int = 0,
        engine: Engine = Engine.GOOGLE,  # this is required
        device: str = "desktop",
        no_cache: bool = False,
        asynch: bool = False,
        output: str = "JSON",
):
    return SerpAPI(connection).search(
        query=query,
        location=location,
        google_domain=google_domain,
        gl=gl,
        hl=hl,
        lr=lr,
        tbs=tbs,
        safe=safe,
        nfpr=nfpr,
        filter=filter,
        tbm=tbm,
        start=start,
        num=num,
        ijn=ijn,
        engine=engine,
        device=device,
        no_cache=no_cache,
        asynch=asynch,
        output=output,
    )


register_builtin_method(search)
