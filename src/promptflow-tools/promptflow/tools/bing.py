import json
import sys

from promptflow.core.tool import ToolProvider, tool
from promptflow.connections import BingConnection
from promptflow.core.cache_manager import enable_cache
from promptflow.core.tools_manager import register_builtin_method, register_builtins
from promptflow.exceptions import ErrorTarget, PromptflowException, SystemErrorException, UserErrorException
from promptflow.tools.common import to_bool
from promptflow.utils.utils import deprecated


class Bing(ToolProvider):
    """
    API Reference:
    https://learn.microsoft.com/en-us/rest/api/cognitiveservices-bingsearch/bing-web-api-v7-reference
    Parameter:
    https://learn.microsoft.com/en-us/rest/api/cognitiveservices-bingsearch/bing-web-api-v7-reference#query-parameters
    """

    def __init__(self, connection: BingConnection):
        super().__init__()
        self.connection = connection

    @staticmethod
    @deprecated(replace="Bing()")
    def from_config(config: BingConnection):
        return Bing(config)

    def calculate_cache_string_for_search(self, **kwargs):
        return json.dumps(kwargs)

    def extract_error_message_and_code(self, error_json):
        error_message = ""
        if not error_json:
            return error_message
        error_code_reference = (
            "For more info, please refer to "
            "https://learn.microsoft.com/en-us/bing/search-apis/"
            "bing-web-search/reference/error-codes"
        )
        if "message" in error_json:
            # populate error_message with the top error items
            error_message += (" " if len(error_message) > 0 else "") + error_json["message"]
        if "code" in error_json:
            # Append error code if existing
            code_message = f"code: {error_json['code']}. {error_code_reference}"
            error_message += (" " if len(error_message) > 0 else "") + code_message
        return error_message

    def extract_error_message(self, error_data):
        error_message = ""
        # For request was rejected. For example, the api_key is not valid
        if "error" in error_data:
            error_message = self.extract_error_message_and_code(error_data["error"])

        # For request accepted but bing responded with non-success code.
        # For example, the parameters value is not valid
        if "errors" in error_data and error_data["errors"] and len(error_data["errors"]) > 0:
            # populate error_message with the top error items
            error_message = self.extract_error_message_and_code(error_data["errors"][0])
        return error_message

    def safe_extract_error_message(self, response):
        default_error_message = "Bing search request failed. Please check logs for details."
        try:
            error_data = response.json()
            print(f"Response json: {json.dumps(error_data)}", file=sys.stderr)
            error_message = self.extract_error_message(error_data)
            error_message = error_message if len(error_message) > 0 else default_error_message
            print(f"Extracted error message: {error_message}", file=sys.stderr)
            return error_message
        except Exception as e:
            # Swallow any exception when extract detailed error message
            print(
                f"Unexpected exception occurs while extract error message "
                f"from response: {type(e).__name__}: {str(e)}",
                file=sys.stderr,
            )
            return default_error_message

    @tool
    @enable_cache(calculate_cache_string_for_search)
    def search(
        self,
        query: str,
        answerCount: int = None,
        cc: str = None,  # country code
        count: int = 10,
        freshness: str = None,
        mkt: str = None,  # market defined by <language code>-<country code>
        offset: int = 0,
        promote: list = [],
        responseFilter: list = [],
        safesearch: str = "Moderate",
        setLang: str = "en",
        textDecorations: bool = False,
        textFormat: str = "Raw",
    ):
        import requests

        # there are others header parameters as well
        headers = {"Ocp-Apim-Subscription-Key": str(self.connection.api_key)}
        params = {
            "q": query,
            "answerCount": int(answerCount) if answerCount else None,
            "cc": cc,
            "count": int(count),
            "freshness": freshness,
            "mkt": mkt,
            "offset": int(offset),
            "promote": list(json.loads(promote)) if promote else [],
            "responseFilter": list(json.loads(responseFilter)) if responseFilter else [],
            "safesearch": safesearch,
            "setLang": setLang,
            "textDecorations": to_bool(textDecorations),
            "textFormat": textFormat,
        }

        try:
            response = requests.get(self.connection.url, headers=headers, params=params)
            if response.status_code == requests.codes.ok:
                return response.json()
            else:
                # Handle status_code is not ok
                # Step I: Try to get accurate error message at best
                error_message = self.safe_extract_error_message(response)

                # Step II: Construct PromptflowException
                if response.status_code >= 500:
                    raise SystemErrorException(message=error_message, target=ErrorTarget.TOOL)
                else:
                    raise UserErrorException(message=error_message, target=ErrorTarget.TOOL)
        except Exception as e:
            if not isinstance(e, PromptflowException):
                error_message = "Unexpected exception occurs. Please check logs for details."
                print(f"Unexpected exception occurs: {type(e).__name__}: {str(e)}", file=sys.stderr)
                raise SystemErrorException(message=error_message, target=ErrorTarget.TOOL)
            raise


register_builtins(Bing)


@tool
def search(
    connection: BingConnection,
    query: str,
    answerCount: int = None,
    cc: str = None,  # country code
    count: int = 10,
    freshness: str = None,
    mkt: str = None,  # market defined by <language code>-<country code>
    offset: int = 0,
    promote: list = [],
    responseFilter: list = [],
    safesearch: str = "Moderate",
    setLang: str = "en",
    textDecorations: bool = False,
    textFormat: str = "Raw",
):
    return Bing(connection).search(
        query=query,
        answerCount=answerCount,
        cc=cc,
        count=count,
        freshness=freshness,
        mkt=mkt,
        offset=offset,
        promote=promote,
        responseFilter=responseFilter,
        safesearch=safesearch,
        setLang=setLang,
        textDecorations=textDecorations,
        textFormat=textFormat,
    )


register_builtin_method(search)
