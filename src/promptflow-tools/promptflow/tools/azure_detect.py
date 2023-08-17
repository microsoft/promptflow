# TODO: previous contract tool meta is not updated as the same time of tool code changes.
# Will remove the file when new named source code is released to all regions.
# Probably around Aug 15.
import traceback

from promptflow._internal import ToolProvider, tool
from promptflow.connections import CustomConnection
from promptflow.core.tools_manager import register_builtins

debug = False


class AzureDetect(ToolProvider):
    """
    Doc reference :
    https://learn.microsoft.com/en-us/azure/cognitive-services/translator/text-sdk-overview?tabs=python
    """

    def __init__(self, connection: CustomConnection):
        super().__init__()
        self.connection = connection

    @tool
    def get_language(self, input_text: str):
        import uuid

        import requests

        traceId = str(uuid.uuid4())
        try:
            # If you encounter any issues with the base_url or path, make sure
            # that you are using the latest endpoint:
            # https://docs.microsoft.com/azure/cognitive-services/translator/reference/v3-0-detect
            print(f"{traceId}: Detect language")
            path = "/detect?api-version=3.0"
            constructed_url = self.connection.api_endpoint + path
            if debug:
                print(f"{traceId} {constructed_url}")

            headers = {
                "Ocp-Apim-Subscription-Key": self.connection.api_key,
                "Ocp-Apim-Subscription-Region": self.connection.api_region,
                "Content-type": "application/json",
                "X-ClientTraceId": traceId,
            }
            if debug:
                print(f"{traceId} {headers}")

            body = [{"text": input_text}]
            request = requests.post(constructed_url, headers=headers, json=body)
            response = request.json()
            if debug:
                print(f"{traceId} {response}")
            # return the detected language IFF we support translation for that language.
            if response[0]["isTranslationSupported"] is True:
                return response[0]["language"]
            else:
                return ""
        except Exception:
            error_msg = traceback.format_exc()
            return f"{traceId} Exception {error_msg}"


register_builtins(AzureDetect)
