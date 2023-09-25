# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import waitress

from promptflow._sdk._constants import LOCAL_SERVICE_PORT
from promptflow._sdk._service.app import create_app


def main():
    app = create_app()
    waitress.serve(app, port=LOCAL_SERVICE_PORT)


if __name__ == "__main__":
    main()
