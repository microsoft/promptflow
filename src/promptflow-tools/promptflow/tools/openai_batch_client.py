from openai import OpenAI as OpenAIClient
from openai import APIError
from openai.types.chat import ChatCompletion
import json
import os
import time
import uuid


class OpenAIBatchClient:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client

    def chat(self, kwargs):
        # construct the batch file content
        batch_file_content = {
            'custom_id': 'promptflow_batch_chat',
            'method': 'POST',
            'url': '/v1/chat/completions',
            'body': kwargs
        }
        # create the batch file
        temp_file_name = f'promptflow_batch_inputs_{uuid.uuid4().hex[:8]}.jsonl'
        with open(temp_file_name, 'w') as batch_input:
            batch_input.write(json.dumps(batch_file_content) + '\n')
        # upload batch file
        with open(temp_file_name, 'rb') as batch_input:
            uploaded_file = self.client.files.create(file=batch_input, purpose='batch')
            batch_res = self.client.batches.create(
                input_file_id=uploaded_file.id,
                endpoint="/v1/chat/completions",
                completion_window="24h",
                metadata={
                  "description": "promptflow batch chat test job"
                }
            )

        # wait for the batch job to complete
        job_status = ""
        output_file_id = ""
        error_file_id = ""
        while job_status != "completed" or job_status != "failed" or job_status != "cancelled" or job_status != "expired":
            job_status = self.client.batches.retrieve(batch_res.id).status
            if job_status == "completed":
                output_file_id = self.client.batches.retrieve(batch_res.id).output_file_id
                error_file_id = self.client.batches.retrieve(batch_res.id).error_file_id
                break
            time.sleep(60)

        if output_file_id:
            # retrieve the output file content
            output_content = self.client.files.content(output_file_id)

            lines = output_content.response.text.split('\n')

            result = json.loads(lines[0])
            body = result['response']['body']

            chat_completion = ChatCompletion(
                id=body['id'],
                choices=body['choices'],
                created=body['created'],
                model=body['model'],
                object=body['object'],
                system_fingerprint=body['system_fingerprint'],
                usage=body['usage']
            )

            # delete the batch file
            self.client.files.delete(output_file_id)
            self.client.files.delete(uploaded_file.id)
            os.remove(temp_file_name)
        elif error_file_id:
            # retrieve the error file content and raise exception
            error_content = self.client.files.content(error_file_id)
            lines = error_content.response.text.split('\n')

            result = json.loads(lines[0])
            body = result['response']['body']
            self.client.files.delete(uploaded_file.id)
            self.client.files.delete(error_file_id)

            raise APIError(message=body['error']['message'], request=None, body=body['error'])

        return chat_completion
