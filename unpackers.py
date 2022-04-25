""" Helper functions for the youtrack_to_jira.py export script.

Author: Micah Svenson
Date Created: 4/25/22 
"""

import ast
import copy
import datetime
import functools
import pandas as pd
import custom_field_processing_functions
from typing import Tuple, Any, Dict


def flatten_series_to_columns(value: Any, field_name: str) -> pd.Series:
    """flattens a series/list to columns with mangled names
    Name mangling in this context means adding `:<number>` to the end of a column name that can be stripped off later.
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

    issue["created"] = timestamp_to_datetime(issue["created"])
    issue["updated"] = timestamp_to_datetime(issue["updated"])
    issue["resolved"] = (
        timestamp_to_datetime(issue["resolved"]) if issue["resolved"] != None else None
    )
    issue["reporter"] = (
        issue["reporter"]["email"] if issue["reporter"]["banned"] is False else None
    )
    issue["updater"] = (
        issue["updater"]["email"] if issue["updater"]["banned"] is False else None
    )

    for custom in issue["customFields"]:
        field_name, field_values = unpack_field_value(custom)
        issue[field_name] = field_values

    del issue["customFields"]

    for link_group in issue["links"]:
        link_name, link_values = unpack_link_group(link_group)
        issue[link_name] = link_values

    del issue["links"]

    issue["tags"] = unpack_tags(issue["tags"]) if "tags" in issue else []
    issue["comments"] = (
        unpack_comments(issue["comments"]) if "comments" in issue else []
    )
    issue["worklogs"] = (
        unpack_worklogs(issue["worklogs"]) if "worklogs" in issue else []
    )

    return issue


def unpack_worklogs(logs: Any) -> list:
    """unpack youtrack worklogs into Jira import format

    Args:
        logs (Any): youtrack logs

    Returns:
        list: A list of Jira formatted worklogs
    """

    unpacked_logs = []
    for log in logs:
        name = log["creator"]["fullName"]
        worktype = (
            log["type"]["name"]
            if log["type"] != None and "name" in log["type"]
            else "No Worktype"
        )
        message = log["text"]
        entrytime = timestamp_to_datetime(log["date"] + (24 * 3600) * 1000)
        user = log["creator"]["email"] if log["creator"]["banned"] is False else ""
        duration = log["duration"]["minutes"] * 60
        unpacked_logs.append(
            f"{name} [{worktype}]: {message};{entrytime};{user};{duration}"
        )

    return unpacked_logs


def list_custom_funcs() -> list:
    """get a definition ordered list of custom functions from the custom_field_procesing_functions.py file"

    Returns:
        list: list of custom function names
    """
    custom_functions_file = "custom_field_processing_functions.py"
    with open(custom_functions_file) as f:
        ast_tree = ast.parse(f.read(), filename=custom_functions_file)
    return [func.name for func in ast_tree.body if isinstance(func, ast.FunctionDef)]


def apply_custom_field_processors(
    issue: Dict[str, Any], issue_lookup_map={}
) -> Dict[str, Any]:
    """apply custom field processing function defined in custom_field_processing_functions.py

    Args:
        issue (Dict[str, Any]): The issue to apply processing functions to

    Raises:
        Exception: when number of keys and values returned by a custom function are not equal

    Returns:
        Dict[str, Any]: The updated issue
    """

    # define helper functions to pass to custom functions
    def key_filter(key: str) -> bool:
        """filter out custom functions and objects that don't apply to the current processed_issue"""
        unmangled_key = key.replace("__", "_").replace("_", " ")
        return unmangled_key in issue

    def get_raw_issue(issue_id, lookup_map={}):
        if issue_id not in lookup_map:
            raise ValueError(f"Issue {issue_id} does not exist in current scope")
        return lookup_map[issue_id]

    get_other_issue = functools.partial(get_raw_issue, lookup_map=issue_lookup_map)

    def get_value(key, lookup_map={}):
        return lookup_map[key]

    get_value_current_issue = functools.partial(get_value, lookup_map=issue)

    all_custom_funcs = list_custom_funcs()

    # evaluate DELETE_IF if the special custom function has been defined
    if "DELETE_IF" in all_custom_funcs:
        delete_issue = getattr(custom_field_processing_functions, "DELETE_IF")(
            get_value_current_issue, get_other_issue
        )
        if delete_issue:
            return None

    # copy the issue so that custom functions don't interact unexpectedly
    processed_issue = copy.deepcopy(issue)

    funcs_to_apply = filter(key_filter, list_custom_funcs())

    for func_name in funcs_to_apply:
        key_name = func_name.replace("__", "_").replace("_", " ")
        new_key_names, new_values = getattr(
            custom_field_processing_functions, func_name
        )(issue[key_name], get_value_current_issue, get_other_issue)
        new_key_names = (
            [new_key_names] if not isinstance(new_key_names, list) else new_key_names
        )
        new_values = [new_values] if not isinstance(new_values, list) else new_values

        if len(new_key_names) != len(new_values):
            raise Exception(
                f"Custom field processing functions must return an equal number of keys and values. {func_name} returned {len(new_key_names)} key names and {len(new_values)} values"
            )

        # delete source data so that the next step can cleanly combine new data going into other pre-existing columns
        del processed_issue[key_name]

        for index, key in enumerate(new_key_names):
            processed_issue[key] = new_values[index]

    return processed_issue


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

    if field["value"] == None:
        field_name = field["name"]
        new_values = [None]

    elif field["$type"] == "SimpleIssueCustomField":
        field_name = field["name"]
        new_values = [field["value"]]

    elif field["$type"] == "StateIssueCustomField":
        field_name = field["name"]
        new_values = [field["value"]["name"]]

    elif field["$type"] == "StateMachineIssueCustomField":
        field_name = field["name"]
        if field["value"]["$type"] == "StateBundleElement":
            new_values = [field["value"]["name"]]
        else:
            new_values = [field["value"]]

    elif field["$type"] == "TextIssueCustomField":
        field_name = field["name"]
        new_values = [field["value"]["text"]]

    elif field["$type"] == "PeriodIssueCustomField":
        field_name = field["name"]
        # convert to seconds
        new_values = [field["value"]["minutes"] * 60]

    elif field["$type"] == "SingleEnumIssueCustomField":
        field_name = field["name"]
        new_values = [field["value"]["name"]]

    elif field["$type"] == "MultiEnumIssueCustomField":
        field_name = field["name"]
        new_values = [item["name"] for item in field["value"]]

    elif field["$type"] == "MultiUserIssueCustomField":
        field_name = field["name"]
        new_values = [
            item["email"] for item in field["value"] if item["banned"] is False
        ]

    elif field["$type"] == "MultiVersionIssueCustomField":
        field_name = field["name"]
        new_values = [item["name"] for item in field["value"]]

    else:
        raise NotImplementedError(f'Dont know how to handle {field["$type"]}')

    if len(new_values) == 1:
        new_values = new_values[0]
    elif len(new_values) == 0:
        new_values = None

    return (field_name, new_values)


def unpack_link_group(link_group: dict) -> Tuple[str, Any]:
    """Unpack a link group name and list of associated issue id's
    Finds the proper direction of the current link type and pairs a list of issue ids in a tuple.

    Args:
        link_group (dict): a youtrack link group response object

    Returns:
        Tuple[str, list]: first value is link type, second value is list of issue ids associated with current issue via link type
    """

    links = [linked_issue["idReadable"] for linked_issue in link_group["issues"]]

    # make link return more descriptive in the event of some special cases
    if len(links) == 0:
        links = None
    elif len(links) == 1:
        links = links[0]

    return (
        link_group["linkType"]["targetToSource"]
        if "INWARD" in link_group["direction"]
        else link_group["linkType"]["sourceToTarget"],
        links,
    )


def unpack_comments(comments: list) -> list:
    """Unpack youtrack issue comments into a jira compatible formate

    jira comment import format is: date;author;comment

    Args:
        comments (list): A list of comments in youtrack response format

    Returns:
        list : a list of comments in jira import format
    """
    unpacked_comments = []
    for comment in comments:
        author = comment["author"]["email"] if not comment["author"]["banned"] else ""
        unpacked_comments.append(
            f'{timestamp_to_datetime(comment["created"])}; {author}; {comment["author"]["fullName"]}: \n{comment["text"]}'
        )

    return unpacked_comments


def timestamp_to_datetime(timestamp: int) -> str:
    """convert timestamps to string formatted dates

    Args:
        timestamp (int): a unix time stamp in milliseconds

    Returns:
        str : a formatted datetime string
    """
    return datetime.datetime.fromtimestamp(int(timestamp / 1000)).strftime(
        "%m/%d/%Y %H:%M:%S"
    )


def unpack_tags(tags: list) -> list:
    """unpack tags into a list of tag names

    Args:
        tags (dict): YouTrack tags result

    Returns:
        list : a list of tag names
    """
    return [tag["name"].replace(" ", "-") for tag in tags]
