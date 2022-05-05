from pathlib import Path

# sprints = [
#     {
#         "name": "ATAT Sprint 1"
#         "start_date": ""
#         "end_date": ""
#     },
#     {
#         "name": "ATAT Sprint 2"
#         "start_date": ""
#         "end_date": ""
#     },
#     {
#         "name": "ATAT Sprint 3"
#         "start_date": ""
#         "end_date": ""
#     }
# ]

# def create_sprints(sprints):
#     return {}


def get_resource(resource_path):
    import base64
    import requests
    base_url =  "https://pandatrack.atlassian.net/rest/agile/1.0/sprint"
    jira_token_path = Path('.jiratoken')
    with open(jira_token_path) as file:
        auth_string = file.readline().strip()
    b64_bytes = base64.b64encode(auth_string.encode('utf-8'))
    b64_auth_string = str(b64_bytes, "utf-8")

    headers = {
        "Authorization": f"Basic {b64_auth_string}",
        "Content-Type": "application/json"
    }

    response = requests.get(f'{base_url}', headers=headers)
    response.raise_for_status()
    return response.json()


response =  get_resource("test")
print(response)