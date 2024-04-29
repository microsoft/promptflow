# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# there is an issue on pip that, when installing promptflow < 1.8.0 with promptflow >= 1.8.0 installed, it will try to
# uninstall promptflow first, but will keep the directory _utils. Then both the _utils directory and old _utils.py file
# will exist in the site-packages directory and cause import error.
# So we need to rename the directory to _utility to avoid this issue.
# On the other hand, promptflow-runtime imported some functions from _utils previously, so we need to keep both _utils
# directory and _utils.py file for backward compatibility.
