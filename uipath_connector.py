# uipath_connector.py
import requests
import streamlit as st
import json
import time

def get_oauth_token(secrets):
    """Authenticates with UiPath Orchestrator and returns an access token."""
    auth_url = "https://cloud.uipath.com/identity_/connect/token"
    auth_payload = {
        "grant_type": "client_credentials",
        "client_id": secrets["client_id"],
        "client_secret": secrets["client_secret"],
        "scope": "OR.Jobs.Read OR.Jobs.Write"
    }
    response = requests.post(auth_url, data=auth_payload)
    response.raise_for_status()
    return response.json()["access_token"]

def run_robot_and_get_output(user_query: str):
    """Starts a UiPath robot, waits for it to complete, and returns the output."""
    secrets = st.secrets["uipath_orchestrator"]
    token = get_oauth_token(secrets)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-UIPATH-OrganizationUnitId": str(secrets["folder_id"])
    }
    
    orchestrator_base_url = f"https://cloud.uipath.com/{secrets['account_name']}/{secrets['tenant_name']}/orchestrator_/odata"

    # 1. Start the Job
    start_job_url = f"{orchestrator_base_url}/Jobs/UiPath.Server.Configuration.OData.StartJobs"
    start_job_payload = {
        "startInfo": {
            "ReleaseKey": secrets["process_key"],
            "Strategy": "ModernJobsCount",
            "JobsCount": 1,
            "InputArguments": json.dumps({"in_UserQuery": user_query})
        }
    }
    
    start_response = requests.post(start_job_url, headers=headers, json=start_job_payload)
    start_response.raise_for_status()
    job_id = start_response.json()["value"][0]["Id"]

    # 2. Poll for Job Completion
    get_job_url = f"{orchestrator_base_url}/Jobs({job_id})"
    while True:
        time.sleep(5) # Wait for 5 seconds before checking status
        job_status_response = requests.get(get_job_url, headers=headers)
        job_status_response.raise_for_status()
        job_data = job_status_response.json()
        
        state = job_data.get("State")
        if state in ["Successful", "Faulted", "Stopped"]:
            if state == "Successful":
                output_args_str = job_data.get("OutputArguments", "{}")
                output_args = json.loads(output_args_str)
                return json.loads(output_args.get("out_QueryResultJson", "{}"))
            else:
                raise Exception(f"UiPath job failed with state: {state}")
