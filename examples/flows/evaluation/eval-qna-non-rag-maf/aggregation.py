import math
from typing import Any, Dict, List, Optional


def aggregate(**kwargs) -> Dict[str, Any]:
    """Compute nanmean for each metric across all rows."""
    metrics = {}
    for name, values in kwargs.items():
        valid = []
        for v in values:
            try:
                fv = float(v)
                if not math.isnan(fv):
                    valid.append(fv)
            except (TypeError, ValueError):
                pass
        if valid:
            metrics[name] = round(sum(valid) / len(valid), 2)
        else:
            metrics[name] = float("nan")
    return metrics
