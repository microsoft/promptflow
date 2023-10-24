from enum import Enum
from promptflow.contracts.types import FilePath

import openai
import requests

from promptflow.connections import AzureOpenAIConnection
# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import tool
from promptflow.tools.common import handle_openai_error
# from promptflow.tools.exception import InvalidWhisperEndpoint


class WhisperEndpoint(str, Enum):
    Transcription = "transcription"
    Translation = "translation"

class ResponseFormat(str, Enum):
    Text = "text"
    Srt = "srt"
    Vtt = "vtt"
    Verbose_json = "verbose_json"


@tool
@handle_openai_error()
def whisper(connection: AzureOpenAIConnection, file: FilePath, endpoint: WhisperEndpoint, deployment_name: str, prompt: str, response_format: ResponseFormat):
    audio_file = open(file, 'rb')
    payload = {'file': audio_file}
    if endpoint == WhisperEndpoint.Transcription:
            # Request URL
        api_url = f"{connection.api_case}/openai/deployments/{deployment_name}/audio/transcriptions?api-version={connection.api_version}"
        headers =  {"api-key": connection.api_key,
                    "Content-Type": "multipart/form-data"}
        response = requests.post(api_url, data=payload, headers=headers)

        print("response json: ", response)

        return response
    else:
        error_message = f"Not Support endpoint '{endpoint}' for whisper api. " \
                        f"Endpoint should be in [Transcription, Translation]."
        raise Exception(message=error_message)
