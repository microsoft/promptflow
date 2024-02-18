# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Dict, Any
from .client import get_client, get_client_with_workspace_info


class Span():
    __container__ = "Span"

    name: str = None
    context: dict = None
    kind: str = None
    parent_id: str = None
    start_time: str = None
    end_time: str = None
    status: dict = None
    attributes: dict = None
    events: list = None
    links: list = None
    resource: dict = None
    id: str = None
    partition_key: str = None

    def __init__(self, 
                 name: str, 
                 context: dict, 
                 kind: str, 
                 parent_id: str, 
                 start_time: str, 
                 end_time: str, 
                 status: dict, 
                 attributes: dict, 
                 events: list = None, 
                 links: list = None, 
                 resource: dict = None,
                 **kwargs):
        self.name = name
        self.context = context
        self.kind = kind
        self.parent_id = parent_id
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
        self.attributes = attributes
        self.events = events
        self.links = links
        self.resource = resource
        self.id = attributes.get("line_run_id", None) if attributes else None
        self.partition_key = attributes.get("session_id", None) if attributes else None

    def persist(self):
        if self.id is None or self.partition_key is None or self.resource is None:
            return
        
        resource_attributes = self.resource.get("attributes", None)
        if resource_attributes is None:
            return
        
        client = get_client_with_workspace_info(self.__container__, resource_attributes)
        return client.create_item(body = self.to_dict())
        
    @classmethod
    def from_cosmosdb(self, id: str, partition_key: str, 
                      subscription_id: str,
                      resource_group_name: str,
                      workspace_name: str) -> "Span":
        client = get_client(Span.__container__, subscription_id, resource_group_name, workspace_name)
        data = client.read_item(id, partition_key)
        params = {}
        for key, value in data.items():
            params[key] = value
        return Span(**params)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v}
    
    



    