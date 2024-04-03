from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class GroupType(str, Enum):
    CONTROL = 'control'
    TREATMENT = 'treatment'


@dataclass
class ExpConfig:
    name: str = None
    variables: Dict = None
    type: GroupType = None

    def get_variable(self, name: str, default: object = None):
        if self.variables and (name in self.variables):
            return self.variables[name]
        return default


@dataclass
class Step:
    name: str = None
    start_time: Optional[datetime] = None
    expire_time: Optional[datetime] = None
    traffic: Dict = None


@dataclass
class Experiment:
    name: str = None
    variants: List[ExpConfig] = None
    steps: List[Step] = None


@dataclass
class ExperimentsDefinition:
    experiments: List[Experiment] = None


@dataclass
class ExperimentsDefinitionCache:
    file_identifier: str = None
    experiments_definition: ExperimentsDefinition = None
    last_updated: datetime = None
