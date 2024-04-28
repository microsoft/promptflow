# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# there is an issue on pip that, when installing promptflow < 1.8.0 with promptflow >= 1.8.0 installed, it will try to
# uninstall promptflow first, but will skip directories with the same name as script name. For example, if we name
# the directory as _utils, it won't be removed when installing promptflow < 1.8.0 with promptflow >= 1.8.0 installed,
# and both the _utils directory and old _utils.py file will exist in the site-packages directory and cause import error.
# So we need to rename the directory to _utility to avoid this issue.
# TODO: rename _utility to _utils after promptflow-runtime start  to give warning
#   on environment with lower version of promptflow
