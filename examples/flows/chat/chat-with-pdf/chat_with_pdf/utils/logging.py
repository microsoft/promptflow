import os


def log(message: str):
    verbose = os.environ.get("VERBOSE")
    if verbose.lower() == "true":
        print(message, flush=True)
