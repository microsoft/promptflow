# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass

from promptflow.azure._constants._trace import CosmosConfiguration, CosmosStatus
from promptflow.azure._restclient.flow.models import TraceCosmosMetaDto


@dataclass
class CosmosMetadata:
    entity_id: str
    configuration: str
    status: str
    database_name: str
    resource_type: str

    @staticmethod
    def _from_rest_object(obj: TraceCosmosMetaDto) -> "CosmosMetadata":
        return CosmosMetadata(
            entity_id=obj.entity_id,
            configuration=obj.trace_cosmos_configuration,
            status=obj.trace_cosmos_status,
            database_name=obj.database_name,
            resource_type=obj.resource_type,
        )

    def is_disabled(self) -> bool:
        return self.configuration == CosmosConfiguration.DISABLED

    def is_ready(self) -> bool:
        return not self.is_disabled() and self.status == CosmosStatus.INITIALIZED
