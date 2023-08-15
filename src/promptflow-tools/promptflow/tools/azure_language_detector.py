import traceback

from promptflow.connections import CustomConnection
from promptflow.core.tool import tool
from promptflow.core.tools_manager import register_builtin_method

debug = False


@tool
def get_language(connection: CustomConnection, input_text: str):
    """
    Doc reference :
    https://learn.microsoft.com/en-us/azure/cognitive-services/translator/text-sdk-overview?tabs=python
    """
    import uuid
    import requests

    traceId = str(uuid.uuid4())
    try:
        # If you encounter any issues with the base_url or path, make sure
        # that you are using the latest endpoint:
        # https://docs.microsoft.com/azure/cognitive-services/translator/reference/v3-0-detect
        print(f"{traceId}: Detect language")
        path = "/detect?api-version=3.0"
        constructed_url = connection.api_endpoint + path
        if debug:
            print(f"{traceId} {constructed_url}")

        headers = {
            "Ocp-Apim-Subscription-Key": connection.api_key,
            "Ocp-Apim-Subscription-Region": connection.api_region,
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


register_builtin_method(get_language)
