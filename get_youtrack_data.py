""" This module can be run as a script to only Download YouTrack data from the API, but is also used automatically in the convert_youtrack_to_jira.py script
Use:
    Configure settings in get_youtrack_data.yml
    Run this script directly to download data
    i.e. $~ python3 get_youtrack_data.py

Author: Micah Svenson
Date Created: 4/25/22 
"""

import re
import json
import yaml
import requests
from typing import Tuple 
from pathlib import Path


def _download_data(config: dict) -> Tuple[list, list]:
    """Downloads issue and work item data from the YouTrack API

    Args:
        config (dict): configuration options from config.yml

    Raises:
        ValueError: _description_

    Returns:
        Tuple[list, list]: _description_
    """
    # load youtrack token
    yt_token_path = Path(config["youtrack_token_path"])
    with open(yt_token_path) as file:
        auth_token = file.readline().strip()
    
    # pull out api request config
    project_name = config["project_name"]
    api_url = config["api_url"]
    num_issues_to_skip = int(config["start_issue"]) - 1
    num_issues_to_retrieve = int(config["num_issues_to_retrieve"])
    requested_issue_fields = re.sub(r"[\n\t\s]*", "", config["issue_fields"])
    requested_work_item_fields = re.sub(r"[\n\t\s]*", "", config["work_item_fields"])
    auth_header = {"Authorization": f"Bearer {auth_token}"}


    # Find Project Id from Project Name
    print("getting youtrack project id...")
    projects_endpoint = f'{api_url}admin/projects'
    projects_list = requests.get(projects_endpoint, params={"fields": "id,name"}, headers=auth_header)

    try: 
        project_id = next(filter(lambda x: project_name in x['name'], projects_list.json()))['id']
    except StopIteration:
        raise ValueError(f"Project {project_name} does not exist")

    # Download Issues
    print(f"Requesting {num_issues_to_retrieve} issues from YouTrack starting with Id {num_issues_to_skip+1}...")
    issues_list_fields = {"fields": requested_issue_fields, "$skip": num_issues_to_skip, "$top": num_issues_to_retrieve}
    issues_endpoint = f'{projects_endpoint}/{project_id}/issues'
    issues_response = requests.get(issues_endpoint, params=issues_list_fields, headers=auth_header)
    issues_response.raise_for_status()
    all_issues = {issue["idReadable"]: issue for issue in issues_response.json()}

    # Download Worklog
    worklog_endpoint = f'{api_url}workItems'
    work_item_fields = {"fields": requested_work_item_fields}
    work_items_response = requests.get(worklog_endpoint, headers=auth_header, params=work_item_fields)
    work_items_response.raise_for_status()
    all_work_items = work_items_response.json()

    # Merge worklogs into issues
    for work_item in all_work_items:
        issue_id = work_item["issue"]["idReadable"]
        if issue_id in all_issues:
            try:
                all_issues[issue_id]["worklogs"].append(work_item)
            except ValueError:
                all_issues[issue_id]["worklogs"] = [work_item]

    return all_issues


def get_issues(config: dict) -> list:
    """get issue data from either from local storage or from the YouTrack API. It prefers locally stored data.

    Args:
        config (dict): configuration from config.yml 

    Returns:
        list: a list of project issues 
    """
    issue_data_path = get_issue_data_path(config)
    try:
        with open(issue_data_path, 'r') as f:
            all_issues = json.load(f)
        print(f"Issue data successfully loaded from {issue_data_path}")
    except Exception:
        print("No local issue data. Attempting Download...")
        all_issues = _download_data(config)

        with open(issue_data_path, 'w') as file:
            json.dump(all_issues, file)

        print(f'YouTrack data written to {issue_data_path}')
    
    return all_issues


def json_to_file(json_data: list, path: Path) -> None:
    """ write json data to file

    Args:
        issues (list): list of youtrack issues
        path (Path): _description_
    """
    with open(path, 'w') as file:
        json.dump(issues, file)


def get_issue_data_path(config: dict) -> Path:
    """ Get path to issue data from configuration. Creates path if it doesnt already exist

    Args:
        config (dict): config from config.yml

    Returns:
        Path: File path issue data file
    """
    base_file_path = Path(config["data_storage_path"])
    base_file_path.mkdir(parents=True, exist_ok=True)
    return base_file_path / f'{config["project_name"]}_youtrack_issues.json'


if __name__ == "__main__":
    with open("config.yml", "r") as file:
        config = yaml.safe_load(file)

    all_issues = _download_data(config)

    with open(get_issue_data_path(config), 'w') as file:
        json.dump(all_issues, file)
