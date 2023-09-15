# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import os.path
import uuid
from pathlib import Path
from typing import Optional


class Configuration(object):

    CONFIG_PATH = Path.home() / ".promptflow" / "config"
    COLLECT_TELEMETRY = "collect_telemetry"
    USER_ID = "user_id"

    def __init__(self):
        self.config = {}
        if not os.path.exists(self.CONFIG_PATH.parent):
            os.makedirs(self.CONFIG_PATH.parent, exist_ok=True)
        if not os.path.exists(self.CONFIG_PATH):
            with open(self.CONFIG_PATH, "w") as config_file:
                json.dump(self.config, config_file)

    @classmethod
    def get_instance(cls):
        return Configuration()

    def set_config(self, key, value):
        self.config[key] = value

        with open(self.CONFIG_PATH, "w") as config_file:
            json.dump(self.config, config_file)

    def get_config(self, key):
        try:
            return self.config.get(key, None)
        except Exception:  # pylint: disable=broad-except
            return None

    def get_telemetry_consent(self) -> Optional[bool]:
        """Get the current telemetry consent value. Return None if not configured."""
        return self.get_config(key=self.COLLECT_TELEMETRY)

    def set_telemetry_consent(self, value):
        """Set the telemetry consent value and store in local."""
        self.set_config(key=self.COLLECT_TELEMETRY, value=value)

    def get_or_set_user_id(self):
        """Get user id if exists, otherwise set user id and return it."""
        user_id = self.get_config(key=self.USER_ID)
        if user_id:
            return user_id
        else:
            user_id = str(uuid.uuid4())
            self.set_config(key=self.USER_ID, value=user_id)
            return user_id
