""" YouTrack to Jira export script
Pull data from the YouTrack API and convert it to a CSV compatible with Jira's CSV import tool. 
Use:
    Configure project settings in youtrack_to_jira.yml
    If additional processing is needed on individual fields, TODO


Author: Micah Svenson
Date Created: 4/25/22 
"""
import os
import re
import csv
import requests
import pandas as pd
import unpackers
from colorama import Fore, Style
import yaml

# configuration
with open("youtrack_to_jira_config.yml", "r") as file:
    config = yaml.safe_load(file)

with open(config["youtrack_token_path"]) as file:
    auth_token = file.readline().strip()

project_name = config["project_name"]
api_url = config["api_url"]
num_issues_to_skip = int(config["start_issue"]) - 1
num_issues_to_retrieve = int(config["num_issues_to_retrieve"])
csv_output_path = config["csv_output_path"]
requested_issue_fields = re.sub(r"[\n\t\s]*", "", config["fields"])
auth_header = {"Authorization": f"Bearer {auth_token}"}

# get project id based on project name
print("Getting YouTrack Project Id...")
projects_list = requests.get(api_url+"admin/projects", params={"fields": "id,name"}, headers=auth_header)

try: 
    project_id = next(filter(lambda x: project_name in x['name'], projects_list.json()))['id']
except StopIteration:
    raise ValueError(f"Project name {project_name} does not exist")


# Request Issues from the API
issues_list_fields={
    "fields": requested_issue_fields,
    "$skip": num_issues_to_skip,
    "$top": num_issues_to_retrieve
    }

print(f"Requesting {num_issues_to_retrieve} issues from YouTrack starting with Id {num_issues_to_skip+1}...")
all_issues = requests.get(api_url+"admin/projects/"+project_id+"/issues", params=issues_list_fields, headers=auth_header).json()

# unpack issues from youtrack's json output format to a simpler json format that can be normalized to csv
print("Unpacking Issues...")
all_unpacked_issues = {issue["idReadable"]: unpackers.unpack_youtrack_issue(issue) for issue in all_issues}

# worklog_fields = {"fields": "id,author(fullName,email,banned),creator(fullName,email,banned),text,type(name),created,updated,duration(minutes),date,issue(idReadable),attributes(name,value)"}
# # TODO: this is really expensive. one api call per issue is slowing everything down
# for issue in all_unpacked_issues:
#     # issue["workItems"] = requests.get(api_url+"issues/"+issue["id"]+"/timeTracking/workItems", headers=auth_header, params=worklog_fields).json()
#     pass

# apply any custom processor functions to data fields
processed_issues = [unpackers.apply_custom_field_processors(all_unpacked_issues[issue_key], issue_lookup_map=all_unpacked_issues) for issue_key in all_unpacked_issues]

# flatten out json. This still leaves some columns as lists/series
print("Flattening Issues...")
all_flattened_unpacked_issues = pd.json_normalize(processed_issues)

# expand list/series values into multiple columns of the same name. (This matches jira's import syntax requirements for mult-value fields)
all_flattened_unpacked_issues.to_csv('./data/test.csv')


print("Expanding Issues...")
expanded_df_list = [
    all_flattened_unpacked_issues[col].apply(unpackers.flatten_series_to_columns, args=[col]) 
    for col in all_flattened_unpacked_issues
    ]
flattened_unpacked_expanded_issues = pd.concat(expanded_df_list, axis=1)

# Unmangle the non-unique column names, write a clean header to a new csv and copy all of the data.
print("Unmangling header row...")
intermediate_csv_path = './data/flattened_unpacked_expanded_issues.csv'
flattened_unpacked_expanded_issues.to_csv(intermediate_csv_path)

with open('./data/flattened_unpacked_expanded_issues.csv','r') as old_file, \
    open('./data/final_jira_issues.csv', 'w') as new_file:
    reader = csv.reader(old_file, delimiter=',')
    writer = csv.writer(new_file, delimiter=',')
    old_header = next(reader)
    new_header = [col.split(":")[0] for col in old_header]
    writer.writerow(new_header)
    [writer.writerow(line) for line in reader]

print("Cleaning up...")
os.remove(intermediate_csv_path)

final_csv_path = './data/final_jira_issues.csv'
print(Fore.GREEN + Style.BRIGHT + f"YouTrack Export Complete. See {final_csv_path}" + Fore.RESET + Style.RESET_ALL)
