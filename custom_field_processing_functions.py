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
5. If multiple function update the same field, only the result from the last executed function will be retained.
    * If it is desired to combine two different results, place a ":0" after the column name of two conflicting functions.
        * For example: One function converts comment syntax from markdown to markup. Another function takes some issue data and writes a new comment.
        * The first function should write its result to the "comments" col/field. The second function should write its result to the "comments:0" col/field.
        * This will ensure that both results show up in the csv under a "comments" column. Note that comments column may not be grouped together.

Examples:
    1. A field called "Task Deliverable Links" needs to be converted into an issue comment
    ```
        def Task_Deliverable_Links(value): 
            return ("comments", f"Task Deliverable Links: {value}") if value != None else ("comments", None)
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

from typing import Any, Tuple, Callable
import re


def DELETE_IF(get_issue_value: Callable, _: Callable) -> bool:
    """Delete the entire current issue if this functions returns True

    Args:
        get_issue_value (Callable): get another column value in the current issue. i.e. get_issue_value(<key name>)
        get_other_issue (Callable): get another issue in the available issue set. i.e. get_other_issue(<issue id>)

    Returns:
        bool: Deletes entire issue if True, does nothing if False
    """
    # Delete YouTrack Epics, because they wont be used in Jira as Components and will just take up extra task numbers
    value = get_issue_value("Type")
    return True if value != None and "Epic" in value else False


def subtask_of(
    value: Any, get_issue_value: Callable, get_other_issue: Callable
) -> Tuple:
    """Traverse issue parent relationships to map YouTrack Hierarchy to Jira Hierarchy
        YouTrack to Jira Mappings
        1. Epic -> Component
            * Jira csv import requires component to be its own column and requires a Name, not an Id. YouTrack Epic summary is mapped to Jira Component column.
        2. Feature -> Epic
            * Jira Epics require a column called "Epic Name" that holds the summary of the Youtrack Feature issue.
            * Jira issues also have "Epic Links" to relate sub issues to the Epic. An "Epic Links" column is populated with the "Epic Name" of an Epic that the current issue is a child of.
        3. User Story -> Story
            * Story mappings are mostly unchanged, just slight naming
        4. Task -> Story (sort of)
            * In the new Jira hierarchy, the project wont use Subtasks of stories, but to preserve the legacy structure of tasks, a new column is created called "youtrack subtask of" to track when a Story had sub-tasks.

    Args:
        value (Any): the current issue value of subtask of
        get_issue_value (Callable): get another column value in the current issue. i.e. get_issue_value(<key name>)
        get_other_issue (Callable): get another issue in the available issue set. i.e. get_other_issue(<issue id>)

    Returns:
        Tuple: New key/column names and associated values
    """

    if value == None:
        return ("subtask of", value)

    # retrieve Feature summary's to create Epic links in Jira
    try:
        component, epic_link, subtask_of_link = helper_flatten_parent_relationships(
            value, get_other_issue
        )
        # print(f"successful link: {epic_link}")
    except Exception as e:
        if value != None:
            print(
                f"Warning: Failed to traverse relationships for {get_issue_value('idReadable')}: {e}"
            )
        component, epic_link, subtask_of_link = (None, None, None)

    return (
        ["Component", "Epic Link", "youtrack subtask of", "subtask of"],
        [component, epic_link, subtask_of_link, value],
    )


def helper_flatten_parent_relationships(
    issue_id: str,
    get_other_issue: Callable,
    epic_link: str = None,
    subtask_of_link: str = None,
) -> Tuple:
    """Helper function that recursively searches through all parent relationships of the current issue

    Args:
        issue_id (str): Id of a parent issue
        get_other_issue (Callable): get another issue in the available issue set. i.e. get_other_issue(<issue id>)
        epic_link (str, optional): Stores an Epic link relationship to the current issue if applicable. Defaults to None.
        subtask_of_link (str, optional): Stores a subtask link relationship for the current issue if applicable. Defaults to None.

    Returns:
        Tuple: Tuple containing all possible issue relationships
    """

    current_issue = get_other_issue(issue_id)
    new_epic_link = epic_link
    new_subtask_of_link = subtask_of_link
    component = None

    if current_issue["Type"] == None:
        return (None, None, None)

    if "User Story" in current_issue["Type"]:
        new_subtask_of_link = current_issue["idReadable"]

    # add "Epic Link" on the way up the hierarchy
    if "Feature" in current_issue["Type"]:
        # return summary to add to the "Epic Link" column
        new_epic_link = current_issue["summary"]

    # Base case. No level higher than a YT Epic
    if "Epic" in current_issue["Type"]:  # or "Component" in current_issue["Type"]:
        component = current_issue["summary"]
        return (component, new_epic_link, new_subtask_of_link)

    # Edge cases
    if any(
        [
            "subtask of" not in current_issue,
            "subtask of" in current_issue and current_issue["subtask of"] == None,
        ]
    ):
        return (component, new_epic_link, new_subtask_of_link)

    # print(f'do the recursive call: {current_issue["Type"]}')
    return helper_flatten_parent_relationships(
        current_issue["subtask of"],
        get_other_issue,
        epic_link=new_epic_link,
        subtask_of_link=new_subtask_of_link,
    )


def Assignees(value: Any, *_) -> Tuple:
    """Overflow multiple assignee's into the "Swarmers" custom field.

    Args:
        value (Any): Assignee names for the current issue
        get_issue_value (Callable): get another column value in the current issue. i.e. get_issue_value(<key name>)
        get_other_issue (Callable): get another issue in the available issue set. i.e. get_other_issue(<issue id>)

    Returns:
        Tuple: New key/column names and associated values
    """

    if value != None and isinstance(value, list) and len(value) > 1:
        # Overflow multiple assignees into swarmers
        return (["Assignees", "Swarmers"], [value[0], value[1:]])
    else:
        # Resassign the original data if only one assignee
        return ("Assignees", value)


def Type(value: Any, get_issue_value: Callable, _) -> Tuple:
    """Map issue types from Youtrack types to Jira Types. 
        YouTrack to Jira Mappings:
        1. Epic -> Component
        2. Feature -> Epic
        3. User Story -> Story
        4. Task -> Story

    Args:
        value (Any): The current issue's Type
        get_issue_value (Callable): get another column value in the current issue. i.e. get_issue_value(<key name>)
        get_other_issue (Callable): get another issue in the available issue set. i.e. get_other_issue(<issue id>)

    Returns:
        Tuple: New key/column names and associated values
    """

    if value == None:
        return ("Type", value)

    if "Feature" in value:
        # Update features to Epics. Jira CSV requires Epics to have an "Epic Name"
        return (["Type", "Epic Name"], ["Epic", get_issue_value("summary")])
    elif "Epic" in value:
        # update Epic's to be components
        return ("Type", "Component")
    else:
        # Dont do anything for other task types
        return ("Type", value)


def Sprints(value: Any, *_) -> Tuple:
    """Convert Sprint names into Sprint Id's for the Jira import tool. Because Jira, there is an Id offset that will need to be manually set based on when you created sprints in Jira.
        Note: For this to work, All sprints referenced in the YouTrack Issue set must be manually created in Jira IN SEQUENCE so that the Id's in the CSV import match.

    Args:
        value (Any): YouTrack Sprint Name
        get_issue_value (Callable): get another column value in the current issue. i.e. get_issue_value(<key name>)
        get_other_issue (Callable): get another issue in the available issue set. i.e. get_other_issue(<issue id>)

    Returns:
        Tuple: New key/column names and associated values
    """

    # Jira only takes numbers for sprint ids
    # assign Backlog None
    # Jira uses internal Id's to map sprints via the csv importer for some unknowable reason.
    # This offset is intended to align the internal jiraId with sprint numbers.
    # Note: prequisite is that All desired sprints have been manually created in Jira and that all internal Jira Id's are sequential
    offset = 7
    if value == None:
        return ("Sprints", None)
    if not isinstance(value, list):
        value = [value]
    return (
        "Sprints",
        [
            [
                int(sprint.split(" ")[-1]) + offset
                if "Backlog" not in sprint and "Bug Board" not in sprint
                else None
                for sprint in value
            ]
        ],
    )


def description(value: Any, *_) -> Tuple:
    """Convert Markdown headings (#,##,etc) to Jira Markup headings (h1.,h2., etc) because Jira can't handle markdown through the importer
        Note: This is barebones and doesnt convert other syntax elements. They were close enough for the most part

    Args:
        value (Any): the current issue description
        get_issue_value (Callable): get another column value in the current issue. i.e. get_issue_value(<key name>)
        get_other_issue (Callable): get another issue in the available issue set. i.e. get_other_issue(<issue id>)

    Returns:
        Tuple: New key/column names and associated values
    """

    markup_description = helper_markdown_to_markup(value) if value != None else None
    return ("description", markup_description)


def comments(value: Any, *_) -> Tuple:
    """Convert Markdown headings (#,##,etc) to Jira Markup headings (h1.,h2., etc) because Jira can't handle markdown through the importer
        Note: This is barebones and doesnt convert other syntax elements. They were close enough for the most part

    Args:
        value (Any): the current issue description
        get_issue_value (Callable): get another column value in the current issue. i.e. get_issue_value(<key name>)
        get_other_issue (Callable): get another issue in the available issue set. i.e. get_other_issue(<issue id>)

    Returns:
        Tuple: New key/column names and associated values
    """
    comments = value if isinstance(value, list) else [value]
    new_comments = [helper_markdown_to_markup(comment) for comment in comments]
    return ("comments", [new_comments])


def Task_Deliverable_Links(value: Any, *_) -> Tuple:
    """Convert task deliverable links field into a comment

    Args:
        value (_type_): The content of the current task deliverable links field
        get_issue_value (Callable): get another column value in the current issue. i.e. get_issue_value(<key name>)
        get_other_issue (Callable): get another issue in the available issue set. i.e. get_other_issue(<issue id>)

    Returns:
        Tuple: New key/column names and associated values
    """
    # Make Task Deliverabe Links field a comment in jira
    # write result to comments:0 so result doesnt overwrite other functions writing to comments
    return (
        ("comments:0", f"Task Deliverable Links:\n{helper_markdown_to_markup(value)}")
        if value != None
        else ("comments", None)
    )


def helper_markdown_to_markup(value: str) -> str:
    """converts markdown section headers to markup section headers.

        This function only supports converting section headers. It could be extended to convert other syntax if desired.

    Args:
        value (str): markdown string

    Returns:
        str: markup string
    """
    sub_h1 = re.sub("(?m)^#(?!#)", "h1.", value)
    sub_h2 = re.sub("(?m)^#{2}(?!#)", "h2.", sub_h1)
    sub_h3 = re.sub("(?m)^#{3}(?!#)", "h3.", sub_h2)
    sub_h4 = re.sub("(?m)^#{4}(?!#)", "h4.", sub_h3)
    sub_h5 = re.sub("(?m)^#{5}(?!#)", "h5.", sub_h4)
    all_subs = re.sub("(?m)^#{6}(?!#)", "h6.", sub_h5)
    return all_subs
