"""
Function names in the file MUST match a key in the unpacked YouTrack JSON in order to execute successfully

"""
from typing import Any, Tuple

def Task_Deliverable_Links(value: Any) -> Tuple:
    # (ATAT only) create a comment containing Task Deliverable Links Content
    return ("Comments", f"Task Deliverable Links: {value}") if value != None else ("Comments", None)

def Assignees(value):
    # (ATAT only) overflow multiple assignees into swarmers custom field
    if value != None and isinstance(value, list) and len(value) > 1:
        return (["Assignees", "Swarmers"], [value[0], value[1:]])
    else:
        return ("Assignees", value)