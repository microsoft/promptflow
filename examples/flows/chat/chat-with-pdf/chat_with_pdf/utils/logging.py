import os


def log(message: str):
    verbose = os.environ.get("VERBOSE")
    if verbose == "true":
        print(message, flush=True)
