""" Define custom functions that will apply additional processing to data fields

Create new functions in this file if you would like to apply additional custom processing on the simplified Youtrack JSON.

Rules:
 1. Function names MUST have the same name as a key in the unpacked issue json. (This is not the raw youtrack data, but the resulting issue after the first unpacking step)
    * Any spaces should be replaced with _ (1 underscore)
    * Any underscores should be replaced with __ (2 underscores)
2. Functions must return a single tuple
    * First value is the column name you would like to place resulting data in
    * Second value is the data
3. Return tuples can contain multiple column names if the desire is to update more than one column's data
    * First tuple value can be an list of column names
    * Second tuple value can be a list of data that will be applied to the column name with a matching index
4. If it is desired to retain original data associated with a key, it is your responsibility to include it in the return tuple of the function
    * The default behavior is to delete the source key/value data in the issue before applying the result of a custom function.


Author: Micah Svenson
Date Created: 4/25/22 
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