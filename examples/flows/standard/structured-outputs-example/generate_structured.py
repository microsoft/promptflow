from promptflow import tool
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from dotenv import load_dotenv
import os
from schemas.calibration_certificate import CalibrationCertificate


# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need

# In Python tool you can do things like calling external services or
# pre/post processing of data, pretty much anything you want

@tool
def generate(instruction: str, format: str) -> str:
    load_dotenv("openai.env")
    client = AzureOpenAI(
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key= os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION")
    )
    prompt = f'{instruction} \n {format}'

    response = client.beta.chat.completions.parse(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"), # model = "deployment_name".
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        response_format=CalibrationCertificate
    )
    return f'{response.choices[0].message.content}'
