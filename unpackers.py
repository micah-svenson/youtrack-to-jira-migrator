""" Helper functions for the youtrack_to_jira.py export script.

Author: Micah Svenson
Date Created: 4/25/22 
"""
import os
import datetime
import pandas as pd
from typing import Tuple, Any

def flatten_series_to_columns(value, field_name):
    if pd.api.types.is_list_like(value):
        if len(value) == 0:
            new_index = [field_name]
            value = [None]
        else:
            # mangle duplicate column names so pandas doesnt get mad
            new_index = [f"{field_name}:{i}" for i in range(0, len(value))]
    else:
        new_index = [f"{field_name}:0"]

    return pd.Series(value, index=new_index, dtype=object)

def unpack_youtrack_issue(issue):
    print("\n", issue["idReadable"])
    new_issue = {
        # basic fields that apply to all issues regardless of project
        "Issue Id": issue["idReadable"],
        "Summary": issue["summary"],
        "Description": issue["description"],

        "Reported": timestamp_to_datetime(issue["created"]),
        "Updated": timestamp_to_datetime(issue["updated"]),

        "Reporter": issue["reporter"]["email"], 
        "Updater": issue["updater"]["email"] 
    }

    # unpack custom fields
    for custom in issue["customFields"]:
        field_name, field_values = unpack_field_value(custom)
        new_issue[field_name] = field_values

    # unpack links
    # NOTE: subtasks and parents are already included in the links key
    for link_group in issue["links"]:
        link_name, link_values = unpack_link_group(link_group)
        new_issue[link_name] = link_values

    # unpack tags/labels
    new_issue["Labels"] = unpack_tags(issue["tags"])

    # unpack comments
    new_issue["Comments"] = unpack_comments(issue["comments"])

    # Run additional custom field processing 
    if os.path.exists('./custom_field_processing_functions.py'):
        import custom_field_processing_functions
    for custom_function_name in dir(custom_field_processing_functions):
        unmangled_name = custom_function_name.replace('__', '_').replace('_', ' ')
        if unmangled_name in new_issue:
            new_key_name, new_value = getattr(custom_field_processing_functions, custom_function_name)(new_issue[unmangled_name])
            # delete source data so that the next step can cleanly combine new data going into other pre-existing columns
            del new_issue[unmangled_name]
            if isinstance(new_key_name, list):
                for index, key in enumerate(new_key_name):
                    if key in new_issue:
                        current_value = new_issue[key]
                        if not isinstance(current_value, list):
                            current_value = [current_value]
                        if not isinstance(new_value, list):
                            new_value = [new_value]
                        new_issue[key] = current_value + new_value
                    else:
                        new_issue[key] = new_value[index]
                    print(key, new_issue[key])
            else:
                new_issue[new_key_name] = new_value
                print(new_key_name, new_issue[new_key_name])

    import json
    with open(f'./data/test{new_issue["Issue Id"]}.json', 'w') as f:
        json.dump(new_issue, f)
    # # (ATAT only) create a comment containing Task Deliverable Links Content
    # if "Task Deliverable Links" in issue:
    #     new_issue["Comments"].append(f"Task Deliverable Links:\n{issue['Task Deliverable Links']}")

    # # (ATAT only) overflow multiple assignees into swarmers custom field
    # if "Assignees" in new_issue and \
    #     new_issue["Assignees"] != None and \
    #         isinstance(new_issue["Assignees"], list) and \
    #         len(new_issue["Assignees"]) > 1:
    #     # assign all but the first assignee to swarmers field
    #     new_issue["Swarmers"] = new_issue["Assignees"][1:-1]
    #     # keep only the first assignee in the assignees field
    #     new_issue["Assignees"] = new_issue["Assignees"][0]

    return new_issue


def unpack_field_value(field: dict) -> Tuple[str, Any]:
    """Unpack YouTrack field values based on YouTrack type

    Args:
        field (dict): the field to unpack

    Raises:
        NotImplementedError: thrown if an unknown youtrack type is encountered

    Returns:
        Tuple[str, Any]: first value is name of field, second value is the values or values stored within the field.
    """
    field_name = ""
    new_values = []

    if field['value'] == None:
        field_name = field['name']
        new_values = [None]

    elif field['$type'] == 'SimpleIssueCustomField':
        field_name = field['name']
        new_values = [field['value']]
        
    elif field['$type'] == 'StateIssueCustomField':
        field_name = field['name']
        new_values = [field['value']['name']]

    elif field['$type'] == 'StateMachineIssueCustomField':
        field_name = field['name']
        if field["value"]["$type"] == "StateBundleElement":
            new_values = [field['value']['name']]
        else:
            new_values = [field['value']]

    elif field['$type'] == 'TextIssueCustomField':
        field_name = field['name']
        new_values = [field['value']['text']]

    elif field['$type'] == 'PeriodIssueCustomField':
        field_name = field['name']
        # convert to seconds
        new_values = [field['value']['minutes'] * 60]

    elif field['$type'] == 'SingleEnumIssueCustomField':
        field_name = field['name']
        new_values = [field['value']['name']]

    elif field['$type'] == 'MultiEnumIssueCustomField':
        field_name = field['name']
        new_values = [item['name'] for item in field['value']]

    elif field['$type'] == 'MultiUserIssueCustomField':
        field_name = field['name']
        new_values = [item['email'] for item in field['value']]

    elif field['$type'] == 'MultiVersionIssueCustomField':
        field_name = field['name']
        new_values = [item['name'] for item in field['value']]

    else:
        raise NotImplementedError(f'Dont know how to handle {field["$type"]}')

    if len(new_values) == 1:
        new_values = new_values[0]
    elif len(new_values) == 0:
        new_values = None

    return (field_name, new_values)

def unpack_link_group(link_group: dict) -> Tuple[str, list]:
    """Unpack a link group name and list of associated issue id's
    Finds the proper direction of the current link type and pairs a list of issue ids in a tuple.

    Args:
        link_group (dict): a youtrack link group response object

    Returns:
        Tuple[str, list]: first value is link type, second value is list of issue ids associated with current issue via link type 
    """
    return (
        link_group["linkType"]["targetToSource"] if link_group["direction"] == "INWARD" else link_group["linkType"]["sourceToTarget"],
        [linked_issue["idReadable"] for linked_issue in link_group["issues"]]
    )

def unpack_comments(comments: list) -> list:
    """Unpack youtrack issue comments into a jira compatible formate

    jira comment import format is: date;author;comment

    Args:
        comments (list): A list of comments in youtrack response format

    Returns:
        list : a list of comments in jira import format
    """
    return [f'{timestamp_to_datetime(comment["created"])};{comment["author"]["email"]};{comment["text"]}' for comment in comments] 


def timestamp_to_datetime(timestamp: int) -> str:
    """convert timestamps to string formatted dates

    Args:
        timestamp (int): a unix time stamp in milliseconds

    Returns:
        str : a formatted datetime string
    """
    return datetime.datetime.fromtimestamp(int(timestamp/1000)).strftime('%Y-%m-%d %H:%M:%S')


def unpack_tags(tags: list) -> list:
    """unpack tags into a list of tag names

    Args:
        tags (dict): YouTrack tags result

    Returns:
        list : a list of tag names
    """
    return [tag['name'] for tag in tags]
