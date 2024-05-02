import requests
from requests.auth import HTTPBasicAuth
import time
from getpass import getpass


EYEFLOW_WS = "https://app.eyeflow.ai"


def login(username, password):

    response = requests.post(f"{EYEFLOW_WS}/auth-user/user/login", auth=HTTPBasicAuth(username, password))
    if response.status_code != 201:
        print("Failed to login. Status code: ", response.status_code)
        exit(1)

    json_data = response.json()
    username = json_data["username"]
    env_name = json_data["selectedResource"]["name"]
    env_id = json_data["selectedResource"]["_id"]
    print(f"""Logged in as {username} on {env_name} ({env_id}). If you want to change the resource, please do it on the web interface.""")
    token = json_data["token"]
    return token


def stop_user_endpoint(token):

    try:
        response = requests.put(f"{EYEFLOW_WS}/endpoint/v1/stop", headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 404:
            print("There is no endpoint to stop. Skipping endpoint stop...")
            return
        elif response.status_code != 200:
            print("Failed to stop endpoint. Status code: ", response.status_code)
            return
        print("Endpoint stopped.")
        return
    except Exception as e:
        print(f"Error stopping endpoint: {e}")
        return


def create_user_endpoint(token, flow_id):

    body = {
        "flowId": flow_id
    }
    response = requests.post(f"{EYEFLOW_WS}/endpoint/v1/create", headers={"Authorization": f"Bearer {token}"}, json=body)
    if response.status_code != 201:
        print(f"Failed to create endpoint. Status code: {response.status_code}. Error: {response.text}")
        exit(1)

    endpoint_id = response.json()["endpoint_id"]
    print(f"Endpoint created. ID: {endpoint_id}")


def get_endpoint_data(token):

    response = requests.get(f"{EYEFLOW_WS}/endpoint/v1/user-endpoint", headers={"Authorization": f"Bearer {token}"})
    if response.status_code != 200:
        print("Failed to get endpoint data. Status code: ", response.status_code)
        return
    return response.json()['endpoint']


def main(username, password, flow_id):

    token = login(username, password)
    stop_user_endpoint(token)
    create_user_endpoint(token, flow_id)

    while True:
        endpoint_data = get_endpoint_data(token)
        status = endpoint_data.get("status")
        endpoint_url = endpoint_data.get("endpoint_url")
        if endpoint_url:
            break

        print("Endpoint URL not available yet. Status: ", status)
        time.sleep(3)

    print(f"Endpoint URL: {endpoint_url}")


if __name__ == "__main__":
    username = input("Enter your username: ")
    password = getpass("Enter your password: ")
    flow_id = input("Enter the flow ID: ")
    # flow_id = "64a462efd32bda0019fcf45d"
    main(username, password, flow_id)