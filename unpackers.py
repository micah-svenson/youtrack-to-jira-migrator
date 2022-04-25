import datetime
import pandas as pd


def create_csv_header(all_issues):
    max_field_counts = {}
    # iterate through full list of issues and find the longest array for each field. This will define the number of duplicate columns needed for the header
    for issue_json in all_issues:
        for field in issue_json:
            if field not in max_field_counts:
                max_field_counts[field] = 0
            if isinstance(issue_json[field], list):
                if len(issue_json[field]) > max_field_counts[field]:
                    max_field_counts[field] = len(issue_json[field])
            else:
                max_field_counts[field] = 1

    # generate header using max field counts
    # Note: order preservation means header will align with rows later on.
    header = []
    for max_field in max_field_counts.items():
        field_name, max_count = max_field
        header += [field_name] * max_count

    return (header, max_field_counts)


def unpacked_issue_to_csv(issue_json, max_field_counts):
    # build csv row 
    row = []
    for field in issue_json:
        addi = add_max_field_padding(issue_json[field], max_field_counts[field])
        print(addi)
        row += addi # add_max_field_padding(issue_json[field], max_field_counts[field])
    return row


def add_max_field_padding(values, num_required_cols):
    padded_values = []
    if isinstance(values, list): 
        # add None values to pad to required number of columns
        num_none_values = num_required_cols - len(values)
        if num_none_values > 0:
            padded_values += [None] * num_none_values
    else:
        padded_values = [values]
    
    return padded_values


def flatten_series_to_columns(value, field_name):
    if pd.api.types.is_list_like(value):
        new_index = []
        for i in range(0, len(value)):
            new_index.append(f"{field_name}:{i}")
        new_series = pd.Series(value, index=new_index, dtype=object)
    else:
        new_series = pd.Series(value, index=[field_name], dtype=object)

    return new_series 

def unpack_youtrack_issue(issue):
    new_issue = {
        # basic fields that apply to all issues regardless of project
        "Issue Id": issue["idReadable"],
        "Summary": issue["summary"],
        "Description": issue["description"],

        "Reported": timestamp_to_datetime(issue["created"]),
        "Updated": timestamp_to_datetime(issue["updated"]),

        "Reporter": issue["reporter"]["email"], #if issue["reporter"]["banned"] == False else None,
        "Updater": issue["updater"]["email"] #if issue["reporter"]["banned"] == False else None,
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

    # (ATAT only) create a comment containing Task Deliverable Links Content
    if "Task Deliverable Links" in issue:
        new_issue["Comments"].append(f"Task Deliverable Links:\n{issue['Task Deliverable Links']}")

    # (ATAT only) overflow multiple assignees into swarmers custom field
    if "Assignees" in new_issue and \
        new_issue["Assignees"] != None and \
            isinstance(new_issue["Assignees"], list) and \
            len(new_issue["Assignees"]) > 1:
        # assign all but the first assignee to swarmers field
        new_issue["Swarmers"] = new_issue["Assignees"][1:-1]
        # keep only the first assignee in the assignees field
        new_issue["Assignees"] = new_issue["Assignees"][0]

    return new_issue


def unpack_field_value(field):
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
        for item in field['value']:
            new_values.append(item['name'])

    elif field['$type'] == 'MultiUserIssueCustomField':
        field_name = field['name']
        for item in field['value']:
            # repeat the name field name for each value entry.
            # if item["banned"] == False:
            new_values.append(item['email'])

    elif field['$type'] == 'MultiVersionIssueCustomField':
        field_name = field['name']
        for item in field['value']:
            # repeat the name field name for each value entry.
            new_values.append(item['name'])

    else:
        raise NotImplementedError(f'Dont know how to handle {field["$type"]}')


    if len(new_values) == 1:
        new_values = new_values[0]
    elif len(new_values) == 0:
        new_values = None

    return (field_name, new_values)

def unpack_link_group(link_group):
    return (
        link_group["linkType"]["targetToSource"] if link_group["direction"] == "INWARD" else link_group["linkType"]["sourceToTarget"],
        [linked_issue["idReadable"] for linked_issue in link_group["issues"]]
    )

def unpack_comments(comments):
    # jira import format is : date;author;comment
    return [f'{timestamp_to_datetime(comment["created"])};{comment["author"]["email"]};{comment["text"]}' for comment in comments] 


def timestamp_to_datetime(timestamp):
    """Convert timestamps to string formatted dates"""
    return datetime.datetime.fromtimestamp(int(timestamp/1000)).strftime('%Y-%m-%d %H:%M:%S')


def unpack_tags(tags):
    """Unpack tags a list"""
    return [tag['name'] for tag in tags]