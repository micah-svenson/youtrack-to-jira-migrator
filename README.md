# YouTrack to Jira Migrator

This package pulls issue data per project from the YouTrack API and transforms it into a CSV importable by the Jira CSV import tool.

The package also optionally will pull raw YouTrack JSON data a folder with the following format

```
folder/
<Project Id>-<Issue number>.json
...
```

## Setup

1. Create a python virtual environment and install requirements in the requirements.txt file.
2. If using the youtrack API, create an API token and store it in a file called `.youtracktoken` in this project's root directory
2. If pulling raw YouTrack Data from a folder, follow instructions to configure this behavior in step 4
3. If further customization of the processed data is desired, add custom processing functions in the custom_field_processing_functions.py file. See the documentation in that file for further instructions
4. Customize the youtrack_to_jira_config.yml file to fit your desired use case. See that file for inline documentation.

## Running the tool

To run the tool: `python3 youtrack_to_jira.py`
