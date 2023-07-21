import logging

from promptflow.connections import *  # noqa

logging.warning(
    "Module 'promptflow.tools.connections' will be removed in the future, "
    "please import from 'promptflow.connections' instead."
)
