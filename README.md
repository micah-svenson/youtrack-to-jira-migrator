# YouTrack to Jira Migrator

This project contains a set of scripts that allow you to download issue data from YouTrack, then transform the data into a CSV compatible with the JIRA CSV import tool.

## Setup

1. Create a python virtual environment and install requirements in the requirements.txt file.
2. If using the youtrack API, create an API token and store it in a file called `.youtracktoken` in this project's root directory
3. If pulling raw YouTrack Data from a folder, follow instructions to configure this behavior in step 4
4. If further customization of the processed data is desired, add custom processing functions in the `custom_field_processing_functions.py` file. See the documentation in that file for further instructions
5. Customize the `youtrack_to_jira_config.yml` file to fit your desired use case. See that file for inline documentation.

## Using

### If you only want to download youtrack data

Use the `get_youtrack_data.py` script.

1. Update the configuration in `youtrack_data_config.yml` to access the YouTrack API and specify the data storage location. See the yaml file header for instructions.
2. Run the script (in your virtual environment from above)
    ```python
    python3 get_youtrack_data.py
    ```
3. Check to ensure data was downloaded by following the the file path output by the script.

Note: If you would like to download more than one project at a time, passing project keys as command line arguments to the get_youtrack_script.py will override the project name configured in youtrack_data_config.yml and download data for any existing projects.

```python
# Download data for youtrack projects.
python3 get_youtrack_data.py <project-id-1> <project-id-2> ...
```

### If you want to convert YouTrack Data to Jira CSV Data (API and local storage)

Use the convert_youtrack_to_jira.py script.

1. Update the configuration in `youtrack_data_config.yml`.
    * Note: This tool will always use a local file at the configured data storage path if it exists.
    * Tip: Delete or move an existing file if you want to pull fresh data from the API
2. Review the `custom_field_processing_functions.py` file to add/remove custom data transformations to correctly map data from custom fields.
3. Run the script (in your virtual environment from above)
    ```python
    python3 convert_youtrack_to_jira.py
    ```
4. Check the resulting CSV to ensure requirements are met.

Note: If you would like to convert more than one project at a time, passing project keys as command line arguments to the `convert_youtrack_to_jira.py` will override the project name configured in `youtrack_data_config.yml` and convert data for the selected projects
```python
# Convert issues for youtrack projects. 
python3 convert_youtrack_to_jira.py <project-id-1> <project-id-2> ...
```

## Importing into JIRA Cloud

This tool was specifically created to work with the Jira CSV importer accessible from System Settings. Only Jira Admins will have access to this tool.

### Manual steps and bugs to watch out for

Before completing the import process, several items will need to be completed through the Jira due to limitations of the importer and/or Jira API. Below is a list of items to keep in mind when importing issues.

1. If an issue is a child of an Epic, but was created before the Epic, the csv import needs to be re-run to establish those links.
    * Do not re-import worklogs or comments or else they will be re-posted on each task.

2. Estimation and Time Spent fields do not parse correctly, unless a nice even number is the first to be parsed. An issue with an estimation and time spent of 3600 seconds, placed at the very top of the csv resolves this issues (no idea why or how).
    * Note: If importing worklogs, do not map the Time Spent field or it will result in doubling time spent, since Jira also sums up all worklogs and adds them to the time spent field.

3. Jira requires that the date format is provided so that it knows how the dates that are passed in are configured. “MM/dd/yyyy hh:mm” should be used as the time format despite excel showing “MM/dd/yyy hh:mm:ss a”.

4. When importing do not check the "map field value" box for the description field. Checking this box corrupts formatting.

5. All users need to be un-banned from Jira if attempting to import information relating to them  

6. If importing sprints is desired, all sprints must be created manually via the Jira UI first. All of these sprints must also be created sequentially for a given project such that an Id offset can be defined to align YouTrack Sprints with internal Jira Sprint Ids.
    * Both the get_youtrack_data.py and convert_youtrack_to_jira.py script will download a json file contain sprint information for a project. Use this file to populate the sprints in Jira including names, start and end dates, and sprint goals.

### Limitations

1. The Jira import tool only recognizes atlassian's markup syntax for descriptions, comments, etc. To alleviate this in a short amount of time, only section headers are converted from markdown to markup syntax. This was enough to make most description readable. There was no additional effort put towards converting other syntax elements.

2. Tags/labels cannot have spaces in Jira so all spaces in tags were replaced with dashes (-)

3. Because of the way the import tool handles sprints, its difficult to map values from YouTrack across to Jira. see steps in the section above to fix this.

4. If an YouTrack Issue type is mapped to Jira component, the description will not be carried over.
