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
import argparse
import unpackers 
import requests
from typing import Tuple 
from pathlib import Path
from colorama import Fore


def get_data_paths(config: dict) -> Path:
    """ Get path to issue data from configuration. Creates path if it doesnt already exist

    Args:
        config (dict): config from config.yml

    Returns:
        Path: File paths to youtrack data
    """
    base_file_path = Path(config["data_storage_path"])
    base_file_path.mkdir(parents=True, exist_ok=True)
    return {
        "issues": base_file_path / f'{config["project_name"]}_youtrack_issues.json',
        "sprints": base_file_path / f'{config["project_name"]}_youtrack_sprints.json'
    }


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
    projects_list = requests.get(projects_endpoint, params={"fields": "id,name,shortName"}, headers=auth_header)

    try: 
        project_id = next(filter(lambda x: project_name in x['shortName'], projects_list.json()))['id']
    except StopIteration:
        raise ValueError(f"Project {project_name} does not exist. \n Your choices are: {[project['shortName'] for project in projects_list.json()]}")

    # Download Issues
    print(f"Requesting {num_issues_to_retrieve} issues from YouTrack starting with Id {num_issues_to_skip+1}...")
    issues_list_fields = {"fields": requested_issue_fields, "$skip": num_issues_to_skip, "$top": num_issues_to_retrieve}
    issues_endpoint = f'{projects_endpoint}/{project_id}/issues'
    issues_response = requests.get(issues_endpoint, params=issues_list_fields, headers=auth_header)
    issues_response.raise_for_status()
    all_issues = {issue["idReadable"]: issue for issue in issues_response.json()}

    # Download Worklog
    worklog_endpoint = f'{api_url}workItems'
    work_item_fields = {"fields": requested_work_item_fields, "query": f'project: {{{project_name}}}', "$top": -1}
    work_items_response = requests.get(worklog_endpoint, headers=auth_header, params=work_item_fields)
    work_items_response.raise_for_status()
    all_work_items = work_items_response.json()

    # Merge worklogs into issues
    for work_item in all_work_items:
        issue_id = work_item["issue"]["idReadable"]
        if issue_id in all_issues:
            try:
                all_issues[issue_id]["worklogs"].append(work_item)
            except (KeyError, ValueError):
                all_issues[issue_id]["worklogs"] = [work_item]

    # Download Sprint Metadata
    agile_endpoint = f'{api_url}agiles'
    agile_board_fields = {"fields": "id,name,projects(shortName),sprints(name,goal,start,finish,id)"}
    agile_boards_response = requests.get(agile_endpoint, headers=auth_header, params=agile_board_fields)
    agile_boards_response.raise_for_status()
    agile_boards = agile_boards_response.json()

    agile_boards = [board for board in agile_boards for project in board["projects"] if project_name in project["shortName"]]
    for board in agile_boards:
        for sprint in board["sprints"]:
            sprint["start"] = unpackers.timestamp_to_datetime(sprint["start"]) if sprint["start"] != None else None
            sprint["finish"] = unpackers.timestamp_to_datetime(sprint["finish"]) if sprint["start"] != None else None

    return {"issues": all_issues, "sprints": agile_boards}


def get_issues(config: dict) -> list:
    """get issue data from either from local storage or from the YouTrack API. It prefers locally stored data.

    Args:
        config (dict): configuration from config.yml 

    Returns:
        list: a list of project issues 
    """
    paths = get_data_paths(config)

    if not config["prefer_api"] and paths["issues"].is_file():
        with open(paths["issues"], 'r') as f:
            all_issues = json.load(f)
        print(f"Issue data successfully loaded from {paths['issues']}")
    else:
        print(f"Downloading data...")
        all_data = _download_data(config)
        write_to_file(paths, all_data)
        all_issues = all_data["issues"]

    return all_issues


def write_to_file(paths: dict, data: dict) -> None:
    """write data to files keys in paths and data are expected to match
       
    Args:
        paths (dict): dict of file paths. expected to match keys of data
        data (dict): dict of data. expected to match keys of paths
    """
    for index, path in paths.items():
        try:
            with open(path, 'w') as file:
                json.dump(data[index], file)
        except KeyError as e:
            raise ValueError("No matching data for {index} at path {path}")
        print(Fore.GREEN + f'YouTrack {index} written to {path.absolute()}' + Fore.RESET)
            

if __name__ == "__main__":
    with open("youtrack_data_config.yml", "r") as file:
        config = yaml.safe_load(file)
    parser = argparse.ArgumentParser()
    parser.add_argument('project_names', nargs='*', help="Space separated list of YouTrack project keys to convert")
    my_args = parser.parse_args()
    project_names = my_args.project_names if len(my_args.project_names) > 0 else [None]
    for project in project_names:
        config["project_name"] = project if project != None else config["project_name"]
        print(Fore.YELLOW + f'Downloading {config["project_name"]}...' + Fore.RESET)
        try:
            write_to_file(get_data_paths(config), _download_data(config))
        except Exception as e:
            print(Fore.RED + f'Failed to download {config["project_name"]}: {e}' + Fore.RESET)
            

