from enum import Enum
from promptflow.contracts.types import FilePath

import openai

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
def whisper(connection: AzureOpenAIConnection, file: FilePath, endpoint: WhisperEndpoint, prompt: str, response_format: ResponseFormat):
    connection_dict = dict(connection)
    audio_file = open(file, 'rb')
    if endpoint == WhisperEndpoint.Transcription:
        return openai.Audio.transcribe(
            model="whisper",
            file=audio_file,
            prompt = prompt,
            response_format = response_format,
            **connection_dict
        )
    elif endpoint == WhisperEndpoint.Translation:
        return openai.Audio.translate(
            model="whisper",
            file=audio_file,
            prompt = prompt,
            response_format = response_format,
            **connection_dict
        )
    else:
        error_message = f"Not Support endpoint '{endpoint}' for whisper api. " \
                        f"Endpoint should be in [Transcription, Translation]."
        raise Exception(message=error_message)
