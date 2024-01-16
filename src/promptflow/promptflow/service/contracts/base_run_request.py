from typing import Any, Dict

from pydantic import BaseModel


class BaseRunRequest(BaseModel):
    run_id: str
    working_dir: str
    flow_file: str
    environment_variables: Dict[str, Any] = None
    log_path: str
