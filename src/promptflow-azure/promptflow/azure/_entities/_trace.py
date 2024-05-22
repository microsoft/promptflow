# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass

from promptflow.azure._constants._trace import CosmosConfiguration, CosmosStatus
from promptflow.azure._restclient.flow.models import TraceCosmosMetaDto


@dataclass
class CosmosMetadata:
    configuration: str
    status: str

    @staticmethod
    def _from_rest_object(obj: TraceCosmosMetaDto) -> "CosmosMetadata":
        return CosmosMetadata(
            configuration=obj.trace_cosmos_configuration,
            status=obj.trace_cosmos_status,
        )

    def is_disabled(self) -> bool:
        return self.configuration == CosmosConfiguration.DISABLED

    def is_ready(self) -> bool:
        return not self.is_disabled() and self.status == CosmosStatus.INITIALIZED
