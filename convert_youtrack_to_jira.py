""" Run this script to convert YouTrack Issues into Jira issues
Use:
    Configure Youtrack data settings in youtrack_data_config.yml
    Add functions to custom_field_processing_functions.py


Author: Micah Svenson
Date Created: 4/25/22 
"""

import csv
import yaml
import argparse
import unpackers
import pandas as pd
from io import StringIO
from pathlib import Path
from colorama import Fore, Style
from get_youtrack_data import get_issues


def dataframe_to_csv(issues_dataframe: pd.DataFrame, config: dict) -> None:
    """Convert a pandas dataframe with mangled column names to csv with clean column names

    Args:
        issues_dataframe (pd.DataFrame): a dataframe of processed Jira Issues
        config (dict): project configuration
    """
    data_storage_path = Path(config["data_storage_path"])
    final_csv_path = (
        data_storage_path
        / config["project_name"]
        / f'{config["project_name"]}_jira_issues.csv'
    )
    data_string = issues_dataframe.to_csv()
    temp_csv = StringIO(data_string)

    with open(final_csv_path, "w") as new_file:
        reader = csv.reader(temp_csv, delimiter=",")
        writer = csv.writer(new_file, delimiter=",")
        old_header = next(reader)
        # Unmangle the non-unique column names, write a clean header to a new csv and copy all of the data.
        new_header = [col.split(":")[0] for col in old_header]
        writer.writerow(new_header)
        [writer.writerow(line) for line in reader]

    print(
        Fore.GREEN
        + Style.BRIGHT
        + f"YouTrack to Jira Conversion Complete. See {final_csv_path.absolute()}"
        + Fore.RESET
        + Style.RESET_ALL
    )


def main(config):
    """
    Convert YouTrack issues to Jira issues and write csv

    Args:
        config (dict): configuration options from youtrack_data_config.yml
    """

    print("Converting YouTrack Issues to Jira Issues...")
    # load issues from local storage or from the API
    all_issues = get_issues(config)

    # unpack issues from youtrack's json output format to a simpler json format that can be normalized to csv
    print("Unpacking Issues...")
    all_unpacked_issues = {
        key: unpackers.unpack_youtrack_issue(issue) for key, issue in all_issues.items()
    }

    # Fix unique issue with "relates to" links due to both sides of the relationship looking the same
    def fix_relates_links(issue, all_issues):
        if issue["relates to"] != None:
            links = (
                issue["relates to"]
                if isinstance(issue["relates to"], list)
                else [issue["relates to"]]
            )
            issue["relates to"] = list(
                filter(
                    lambda link: issue["idReadable"]
                    not in all_issues[link]["relates to"],
                    links,
                )
            )
        return issue

    [
        fix_relates_links(all_unpacked_issues[issue], all_unpacked_issues)
        for issue in all_unpacked_issues
    ]

    # Apply any custom processor functions to data fields
    processed_issues = [
        unpackers.apply_custom_field_processors(
            all_unpacked_issues[issue_key], issue_lookup_map=all_unpacked_issues
        )
        for issue_key in all_unpacked_issues
    ]
    processed_issues = filter(lambda x: x != None, processed_issues)

    # flatten out json. This still leaves some columns as lists/series
    print("Flattening Issues...")
    issue_df = pd.json_normalize(processed_issues)
    expanded_df_list = [
        issue_df[col].apply(unpackers.flatten_series_to_columns, args=[col])
        for col in issue_df
    ]
    flattened_issues_df = pd.concat(expanded_df_list, axis=1)
    dataframe_to_csv(flattened_issues_df, config)


if __name__ == "__main__":
    # config
    with open("youtrack_data_config.yml", "r") as file:
        config = yaml.safe_load(file)

    # cli arg parsing
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "project_names",
        nargs="*",
        help="Space separated list of YouTrack project keys to convert",
    )
    my_args = parser.parse_args()
    project_names = my_args.project_names if len(my_args.project_names) > 0 else [None]

    # execute
    for project in project_names:
        config["project_name"] = project if project != None else config["project_name"]
        print(Fore.YELLOW + f'Converting {config["project_name"]}...' + Fore.RESET)
        try:
            main(config)
        except Exception as e:
            print(
                Fore.RED
                + f'Failed to convert {config["project_name"]}: {e}'
                + Fore.RESET
            )
