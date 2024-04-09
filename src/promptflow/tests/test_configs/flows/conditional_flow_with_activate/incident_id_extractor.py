from promptflow.core import tool


@tool
def extract_incident_id(incident_content: str, incident_id: int):
    if incident_id >= 0 and incident_id < 3:
        return {
            "has_incident_id": True,
            "incident_id": incident_id,
            "incident_content": incident_content
        }
    return {
        "has_incident_id": False,
        "incident_id": incident_id,
        "incident_content": incident_content
    }