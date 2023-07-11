#!/bin/bash

# <promptflow_install>
pip install promptflow-sdk[azure,builtins]==0.0.99056313 --extra-index-url https://azuremlsdktestpypi.azureedge.net/promptflow/
# </promptflow_install>

pip list