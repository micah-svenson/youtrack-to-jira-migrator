""" Define custom functions that will apply additional processing to data fields

Create new functions in this file if you would like to apply additional custom processing on the simplified Youtrack JSON.

Rules:
 1. Function names MUST have the same name as a key in the unpacked issue json. (This is not the raw youtrack data, but the resulting issue after the first unpacking step)
    * Any spaces should be replaced with _ (1 underscore)
    * Any underscores should be replaced with __ (2 underscores)
2. Functions must return a single tuple
    * First value is the column name you would like to place resulting data in
    * Second value is the data
3. Every function takes a single argument -- conventionally called "value".
    * value is the current value of an element in a column. The column is selected by means of the function name.
3. Return tuples can contain multiple column names if the desire is to update more than one column's data
    * First tuple value can be an list of column names
    * Second tuple value can be a list of data that will be applied to the column name with a matching index
4. If it is desired to retain original data associated with a key, it is your responsibility to include it in the return tuple of the function
    * The default behavior is to delete the source key/value data in the issue before applying the result of a custom function.

Examples:
    1. A field called "Task Deliverable Links" needs to be converted into an issue comment
    ```
        def Task_Deliverable_Links(value): 
            return ("Comments", f"Task Deliverable Links: {value}") if value != None else ("Comments", None)
    ```
        * function name looks like key/column name except spaces are replaced with underscores
        * function accepts a single "value" argument
        * function returns a tuple. (<column name>, <data>)
            * This function places the content of Task Deliverable Links the Comments key/column for the current issue

    2. A field called "Assignees" needs to contain only a single value for Jira. This function overflows additional assignees to a multi user Swarmers key/column
    ```
        def Assignees(value):
            if value != None and isinstance(value, list) and len(value) > 1:
                return (["Assignees", "Swarmers"], [value[0], value[1:]])
            else:
                return ("Assignees", value)
    ```
        * function name looks like key/column name
        * function accepts a single "value" argument
        * function returns a tuple. (<column name>, <data>)
            * In the event of assignee overflow, tuple contains a list of 2 key/column names and a list of 2 corresponding values
            * Note that the length of the lists in each tuple must be equal.
            * Also note that a Swarmers column already exists. Any overflow will be added to existing data in the swarmers column and will not overwrite it.
            * However, the Assignees column is overwritten because its the column that this function is operating on.


Author: Micah Svenson
Date Created: 4/25/22 
"""
from typing import Any, Tuple


def subtask_of(value, get_issue_value, get_other_issue):
    # retrieve Feature summary's to create Epic links in Jira
    # print("subtask of value", value)
    if value == None:
        return ("Epic Link", None)
    try:
        component, epic_link = helper_flatten_parent_relationships(value, get_other_issue)
        # print(f"successful link: {epic_link}")
    except Exception as e:
        print(f"Warning: Failed to create epic link for {value}: {e}")
        component, epic_link = (None, None)
                
    return (["Epic Link", "Component", "subtask of"], [epic_link, component, value])


def Task_Deliverable_Links(value, *_):
    # Make Task Deliverabe Links field a comment in jira
    return ("comments", f";;Task Deliverable Links: {value}") if value != None else ("Comments", None)

def Assignees(value, *_):
    if value != None and isinstance(value, list) and len(value) > 1:
        # Overflow multiple assignees into swarmers
        return (["Assignees", "Swarmers"], [value[0], value[1:]])
    else:
        # Resassign the original data if only one assignee
        return ("Assignees", value)

def Type(value, get_issue_value, _):
    if "Feature" in value:
        # YouTrack features need to be Jira Epics
        return (["Type", "Epic Name"], ["Epic", get_issue_value("summary")])
    elif "Epic" in value:
        # YouTrack epics are components in Jira
        return (["Type", "Component"], ["Component", get_issue_value("summary")])
    else:
        # Dont do anything for other task types
        return ("Type", value)

def Sprints(value, *_):
    # Jira only takes numbers for sprint ids
    # assign Backlog None
    if value == None:
        return ("Sprints", None)

    if not isinstance(value, list):
        value = [value]
    
    return ("Sprints", [[sprint.split(" ")[-1] if "Backlog" not in sprint else None for sprint in value]])


def helper_flatten_parent_relationships(issue_id, get_other_issue, epic_link=None):
    current_issue = get_other_issue(issue_id)

    # add "Epic Link" on the way up the hierarchy 
    if "Feature" in current_issue["Type"]:
        # return summary to add to the "Epic Link" column
        epic_link = current_issue["summary"]

    # Base case. No level higher than a YT Epic
    if "Epic" in current_issue["Type"]:
        return (current_issue["summary"], epic_link)

    # Edge cases
    if any([current_issue == None, "subtask of" not in current_issue, "subtask of" in current_issue and current_issue["subtask of"] == None]):
        return (None, epic_link)

    return helper_flatten_parent_relationships(current_issue["subtask of"], get_other_issue, epic_link=epic_link)

