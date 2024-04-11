from promptflow.client import PFClient

MAX_RESULTS = 20


def run_name_completer(prefix, parsed_args, **kwargs):
    client = PFClient()
    runs = client.runs._search(search_name=prefix, max_results=MAX_RESULTS)

    res = []

    for entity in runs:
        res.append(entity.name)

    return res
