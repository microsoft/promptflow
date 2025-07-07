from promptflow.client import PFClient

_pf_client_instance = None

def get_pf_client() -> PFClient:
    global _pf_client_instance

    if _pf_client_instance is None:
        _pf_client_instance = _initialize_pf_client()
    return _pf_client_instance

def _initialize_pf_client() -> PFClient:
    try:
        _pf_client_instance = PFClient()
    except Exception as e:
        raise RuntimeError(f"Error occured when initializing Promptflow client: {e}")
    
    if _pf_client_instance is None:
        raise RuntimeError("Promptflow client initialization failed")

    return _pf_client_instance
