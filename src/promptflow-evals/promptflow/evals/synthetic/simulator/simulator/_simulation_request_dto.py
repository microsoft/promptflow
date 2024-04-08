# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json


class SimulationRequestDTO:
    def __init__(self, url, headers, payload, params, templatekey, template_parameters):
        self.url = url
        self.headers = headers
        self.json = json.dumps(payload)
        self.params = params
        self.templatekey = templatekey
        self.templateParameters = template_parameters

    def to_dict(self):
        return self.__dict__

    def to_json(self):
        return json.dumps(self.__dict__)
