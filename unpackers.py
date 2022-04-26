""" Helper functions for the youtrack_to_jira.py export script.

Author: Micah Svenson
Date Created: 4/25/22 
"""

import os
import datetime
import pandas as pd
from typing import Tuple, Any, Dict


def flatten_series_to_columns(value: Any, field_name: str) -> pd.Series:
    """flattens a series/list to columns with mangled names
    Name mangling in this context means adding a :int to the end of a column name that can be stripped off later.
    i.e. Assignee:0, Assignee:1, etc


    Args:
        value (Any): Any pandas data frame value. Only list like values will get new columns
        field_name (str): the name of the column 

    Returns:
        pd.Series: an name indexed pandas series 
    """
    index_range = 1

    if pd.api.types.is_list_like(value):
        if len(value) == 0:
            value = [None]
        index_range = len(value)

    # Mangle names of every column even if there is only one value for consistency
    new_index = [f"{field_name}:{i}" for i in range(0, index_range)]

    return pd.Series(value, index=new_index, dtype=object)


def unpack_youtrack_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Unpack youtrack issue api response into a simpler JSON

    This function also applies the custom field processing functions defined in custom_field_processing_functions.py

    Args:
        issue (Dict[str, Any]): A YouTrack issue response

    Returns:
        Dict[str, Any]: A simplified issue JSON
    """

    new_issue = {
        # basic fields that apply to all issues regardless of project
        "Issue Id": issue["idReadable"],
        "Summary": issue["summary"],
        "Description": issue["description"],

        "Reported": timestamp_to_datetime(issue["created"]),
        "Updated": timestamp_to_datetime(issue["updated"]),

        "Reporter": issue["reporter"]["email"] if issue["reporter"]["banned"] is True else None, 
        "Updater": issue["updater"]["email"] if issue["reporter"]["banned"] is True else None,
    }

    # unpack custom fields
    for custom in issue["customFields"]:
        field_name, field_values = unpack_field_value(custom)
        new_issue[field_name] = field_values

    # unpack links
    for link_group in issue["links"]:
        link_name, link_values = unpack_link_group(link_group)
        new_issue[link_name] = link_values

    # unpack tags/labels
    new_issue["Labels"] = unpack_tags(issue["tags"])

    # unpack comments
    new_issue["Comments"] = unpack_comments(issue["comments"])

    # unpack worklogs
    new_issue["Worklogs"] = unpack_worklogs(issue["workItems"])

    # Apply an custom field processing functions
    new_issue = apply_custom_field_processors(new_issue)

    return new_issue

def unpack_worklogs(logs):
    return [
        f'{log["creator"]["fullName"]}-{log["type"]["name"] if "name" in log["type"] else "No Worktype"}: {log["text"]};{timestamp_to_datetime(log["date"])};{log["creator"]["email"] if log["creator"]["banned"] is False else ""};{log["duration"]["minutes"]*60}'
        for log in logs
    ]


def apply_custom_field_processors(issue: Dict[str, Any]) -> Dict[str, Any]:
    """apply custom field processing function defined in custom_field_processing_functions.py

    Args:
        issue (Dict[str, Any]): The issue to apply processing functions to

    Raises:
        Exception: when number of keys and values returned by a custom function are not equal

    Returns:
        Dict[str, Any]: The updated issue
    """

    # only apply custom field processors if they exist
    # TODO: move this import to a higher level so it only gets called once
    if os.path.exists('./custom_field_processing_functions.py'):
        import custom_field_processing_functions
    else:
        return issue

    def key_filter(key: str) -> bool:
        """filter out custom functions and objects that don't apply to the current issue"""
        unmangled_key = key.replace('__', '_').replace('_', ' ')
        return unmangled_key in issue

    funcs_to_apply = filter(key_filter, dir(custom_field_processing_functions))

    import functools
    def get_value(key, map={}):
        return map[key]
    get_issue_value = functools.partial(get_value, map=issue)

    for func_name in funcs_to_apply:
        key_name = func_name.replace('__', '_').replace('_', ' ')
        new_key_names, new_values = getattr(custom_field_processing_functions, func_name)(issue[key_name], get_issue_value)
        new_key_names = [new_key_names] if not isinstance(new_key_names, list) else new_key_names
        new_values = [new_values] if not isinstance(new_values, list) else new_values

        if len(new_key_names) != len(new_values):
            raise Exception(f"Custom field processing functions must return an equal number of keys and values. {func_name} returned {len(new_key_names)} key names and {len(new_values)} values")

        # delete source data so that the next step can cleanly combine new data going into other pre-existing columns
        del issue[key_name]

        for index, key in enumerate(new_key_names):
            # if data is being added to a different existing column, preserve the original data while adding new data.
            current_value = issue[key] if key in issue else []
            current_value = [current_value] if not isinstance(current_value, list) else current_value
            new_value = new_values[index] if isinstance(new_values[index], list) else [new_values[index]]
            issue[key] = current_value + new_value
    return issue


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
        new_values = [item['email'] for item in field['value'] if item['banned'] is False]

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
