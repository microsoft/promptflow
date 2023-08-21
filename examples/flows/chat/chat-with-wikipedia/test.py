from promptflow.azure import PFClient
from azure.ai.ml import MLClient
from azure.identity import DefaultAzureCredential

if __name__ == "__main__":

    cred = DefaultAzureCredential()
    ml = MLClient.from_config(cred)
    pf = PFClient(ml)
    mapping = dict(config={"a": 1}, chat_history='${data.chat_history}', question='${data.question}')
    r = pf.run(flow='.', data='data.jsonl', column_mapping=mapping)
    pf.stream(r)
    print(r)
       