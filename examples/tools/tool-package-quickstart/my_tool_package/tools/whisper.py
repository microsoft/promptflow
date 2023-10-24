from enum import Enum
from typing import Union
from promptflow.contracts.types import FilePath

import openai
import requests

from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
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
def whisper(connection: Union[AzureOpenAIConnection, OpenAIConnection], file: FilePath, endpoint: WhisperEndpoint, deployment_name: str, prompt: str, response_format: ResponseFormat):
    audio_file = open(file, 'rb')
    files = {"file": "@./audio.wav"}
    connection_dict = dict(connection)
    if isinstance(connection, AzureOpenAIConnection):
            # Request URL
        api_url = f"{connection.api_base}/openai/deployments/{deployment_name}/audio/transcriptions?api-version={connection.api_version}"
        print("api_url: ",api_url)
        headers =  {"api-key": connection.api_key,
                    "Content-Type": "multipart/form-data"}
        response = requests.post(api_url, headers=headers, data=files)

        print("response json: ", response.json())

        return response.json()
    elif isinstance(connection, OpenAIConnection):
        response = openai.Audio.transcribe(
            model="whisper-1",
            file=audio_file,
            prompt = prompt,
            response_format = response_format,
            **connection_dict
        )

        print("response json: ", response.json())

        return response.json()
    else:
        error_message = f"Not Support endpoint '{endpoint}' for whisper api. " \
                        f"Endpoint should be in [Transcription, Translation]."
        raise Exception(message=error_message)
