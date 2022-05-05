# YouTrack to Jira Migrator

This package pulls issue data per project from the YouTrack API and transforms it into a CSV importable by the Jira CSV import tool.

The package also optionally will pull raw YouTrack JSON data from a local file

## Setup

1. Create a python virtual environment and install requirements in the requirements.txt file.
2. If using the youtrack API, create an API token and store it in a file called `.youtracktoken` in this project's root directory
2. If pulling raw YouTrack Data from a folder, follow instructions to configure this behavior in step 4
3. If further customization of the processed data is desired, add custom processing functions in the custom_field_processing_functions.py file. See the documentation in that file for further instructions
4. Customize the youtrack_to_jira_config.yml file to fit your desired use case. See that file for inline documentation.

## Using

### If you only want to download youtrack data
Use the get_youtrack_data.py script.
1. Update the configuration in youtrack_data_config.yml to access the YouTrack API and specify the data storage location.
2. Run the script (in your virtual environment from above)
```
python3 get_youtrack_data.py
```
3. Check to ensure data was downloaded by following the the file path output by the script.

### If you want to convert YouTrack Data to Jira CSV Data (API and local storage)
Use the convert_youtrack_to_jira.py script.
1. Update the configuration in youtrack_data_config.yml. 
    * Note: This tool will always use a local file at the configured data storage path if it exists.
    * Tip: Delete or move an existing file if you want to pull fresh data from the API
2. Review the custom_field_processing_functions.py file to add/remove custom functions as desired.
2. Run the script (in your virtual environment from above)
```
python3 convert_youtrack_to_jira.py
```
3. Check the resulting CSV to ensure requirements are met. 


## Importing into JIRA Cloud
This tool was specifically created to work with the Jira CSV importer accessible from System Settings. Only Jira Admins will have access to this tool.

Before completing the import process, several items will need to be completed through the Jira due to limitations of the importer and/or Jira API.

### Sprints
If importing sprints is desired, all sprints must be created manually via the Jira UI first. All of these sprints must also be created sequentially for a given project such that an Id offset can be defined to align YouTrack Sprints with internal Jira Sprint Ids.

### Jira Mapping Configuration
TODO: add to this. also commit an example csv import configuration file if possible
