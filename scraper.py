import json
import requests
import msal
import atexit
import os
import confidential

# Configuraton stuff
AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = ["Tasks.Read"]
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
TOKEN_CACHE_FILE = "token_cache.bin"

cache = msal.SerializableTokenCache()

if os.path.exists(TOKEN_CACHE_FILE):
    with open(TOKEN_CACHE_FILE, "r") as f:
        cache.deserialize(f.read())

atexit.register(lambda: 
                open(TOKEN_CACHE_FILE, "w").write(cache.serialize())
                if cache.has_state_changed else None
                )

app = msal.PublicClientApplication(
    confidential.CLIENT_ID,
    authority=AUTHORITY,
    token_cache=cache
)

def get_access_token():
    accounts = app.get_accounts()
    token_response = None

    if accounts:
        token_response = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not token_response:
        print("No cached token. Starting device flow for new token.")
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "message" not in flow:
            raise ValueError("Failed to create device flow. Error: %s", json.dumps(flow, indent=4))
        
        print(flow["message"]) # This will print the URL and code for you to use on another device
        token_response = app.acquire_token_by_device_flow(flow)

    if "access_token" in token_response:
        return token_response["access_token"]
    else:
        print("Failed to acquire access token.")
        print(token_response.get("error"))
        print(token_response.get("error_description"))
        return None

def get_all_todos(access_token):
    headers = {"Authorization": "Bearer " + access_token}
    all_tasks_by_list = {}

    try:
        list_reponse = requests.get(
            f"{GRAPH_API_ENDPOINT}/me/todo/lists",
            headers=headers
        )
        list_reponse.raise_for_status()
        task_lists = list_reponse.json().get("value", [])

        for task_list in task_lists:
            list_name = task_list.get("displayName")
            list_id = task_list.get("id")
            if not list_name or not list_id:
                continue

            # Get all tasks first, then filter in Python
            tasks_reponse = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/todo/lists/{list_id}/tasks",
                headers=headers
            )
            tasks_reponse.raise_for_status()
            tasks = tasks_reponse.json().get("value", [])

            # Filter out completed tasks in Python
            incomplete_tasks = [task.get("title") for task in tasks if task.get("status") != "completed"]
            all_tasks_by_list[list_name] = incomplete_tasks
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        print(f"Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

    return all_tasks_by_list

if __name__ == "__main__":
    token = get_access_token()
    if token:
        todos = get_all_todos(token)
        if todos is not None:
            print(json.dumps(todos, indent=4))
        else:
            print("Failed to retrieve tasks.")
    else:
        print("No access token available.")