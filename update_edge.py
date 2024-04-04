#!/usr/bin/python3

"""
SiliconLife Eyeflow
Function to update edge data

Author: Alex Sobral de Freitas
"""

import os
import traceback
import sys
import json
import requests
import jwt
import subprocess
import datetime
import tarfile
# from bson import ObjectId
from eyeflow_sdk import edge_client

conf_path = "/opt/eyeflow/run/eyeflow_conf.json"
if not os.path.exists(conf_path):
    conf_path = os.path.join(os.path.dirname(__file__), "eyeflow_conf.json")

if not os.path.exists(conf_path):
    print("Error: eyeflow_conf.json not found")
    sys.exit(1)

with open(conf_path) as fp:
    LOCAL_CONFIG = json.load(fp)

from eyeflow_sdk.log_obj import log
import utils
#----------------------------------------------------------------------------------------------------------------------------------


def upload_file(app_token, task_id, filename):
    log.info(f'Uploading file: {filename} - task: {task_id}')

    try:
        tar_filename = f"{filename}-{task_id}.tar.gz"
        if os.path.isfile(tar_filename):
            os.remove(tar_filename)

        wd = os.getcwd()
        os.chdir(os.path.dirname(filename))
        with tarfile.open(tar_filename, "w:gz") as tar:
            tar.add(os.path.basename(filename))

        os.chdir(wd)

        endpoint = jwt.decode(app_token, options={"verify_signature": False})['endpoint']
        msg_headers = {'Authorization' : f'Bearer {app_token}'}
        url = f"{endpoint}/task/{task_id}/upload"
        print(url)

        files = {
            'file': open(tar_filename, 'rb')
        }

        values = {
            "status": "completed",
            "task_result": json.dumps({
                "execute_date": {
                    "$date": datetime.datetime.now(datetime.timezone.utc)
                },
                "file": filename,
                "filesize": os.stat(filename).st_size
            }, default=str)
        }

        response = requests.post(url, files=files, data=values, headers=msg_headers)

        os.remove(tar_filename)

        if response.status_code != 201:
            raise Exception(f"Failing upload file. Response Json: {response.json()}")

        return

    except requests.ConnectionError as error:
        log.error(f'Failing uploading file: {filename}. Connection error: {error}')
        return
    except requests.Timeout as error:
        log.error(f'Failing uploading file: {filename}. Timeout: {error}')
        return
    except Exception as excp:
        log.error(f'Failing uploading file: {filename} - {excp}')
        return
# ---------------------------------------------------------------------------------------------------------------------------------


def post_task_result(app_token, task_id, retcode, stdout, stderr):
    try:
        task_result = "success" if retcode == 0 else "failure"
        log.info(f"Send task result {task_result}")
        endpoint = jwt.decode(app_token, options={"verify_signature": False})['endpoint']
        msg_headers = {'Authorization' : f'Bearer {app_token}'}
        url = f"{endpoint}/task/{task_id}"

        exec_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
        exec_date = exec_date[:exec_date.index('.')] + "Z"
        event = {
            "status": "completed",
            "task_result": {
                "execute_date": {
                    "$date": exec_date
                },
                "status": task_result,
                "log_data": {
                    "stdout": stdout,
                    "stderr": stderr
                }
            }
        }

        response = requests.post(url, json=event, headers=msg_headers)

        if response.status_code != 201:
            raise Exception(f"Failing insert task result: {response.json()}")

        return True

    except requests.ConnectionError as error:
        log.error(f'Failing inserting task result. Connection error: {error}')
        return None
    except requests.Timeout as error:
        log.error(f'Failing inserting  task result. Timeout: {error}')
        return None
    except Exception as excp:
        log.error(f'Failing inserting task result - {excp}')
        return None
# ---------------------------------------------------------------------------------------------------------------------------------


def execute_tasks(app_token, edge_tasks):
    # log.info(json.dumps(edge_tasks, indent=2))
    for task in edge_tasks:
        if task["task"]["type"] == "install_pack":
            log.info(f'Install pack: {task["task"]["params"]["pack"]["name"]}')
            pack_doc, pack_filename = utils.download_pack(app_token, task["task"]["params"]["pack"], pack_folder=LOCAL_CONFIG["file-service"]["temp_folder"])
            if pack_doc is not None:
                retcode, stdout, stderr = utils.install_pack(pack_doc, pack_filename)
                post_task_result(app_token, task_id=task["_id"], retcode=retcode, stdout=stdout, stderr=stderr)
        elif task["task"]["type"] == "run_command":
            cmd = task["task"]["params"]["command"]
            log.info(f'Run command: {cmd}')
            ret = subprocess.run(cmd, capture_output=True, shell=True)
            if ret.returncode != 0:
                log.error(f"Fail executing command: {ret.stderr.decode()}")
            else:
                log.info(f"Command success: {ret.stdout.decode()}")

            post_task_result(app_token, task_id=task["_id"], retcode=ret.returncode, stdout=ret.stdout.decode(), stderr=ret.stderr.decode())
        elif task["task"]["type"] == "upload_file":
            filename = task["task"]["params"]["filename"]
            log.info(f'Upload file: {filename}')
            upload_file(app_token, task_id=task["_id"], filename=filename)
#----------------------------------------------------------------------------------------------------------------------------------


def main(args=None):
    # prevent multiple instances
    try:
        import socket
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        ## Create an abstract socket, by prefixing it with null.
        s.bind( '\0postconnect_gateway_notify_lock')
    except socket.error as e:
        print(f"Process already running ({e.args[0]}:{e.args[1]} ). Exiting")
        exit(0)

    app_info, app_token = utils.get_license()
    if "edge_id" in app_info:
        log.info(f'Edge ID: {app_info["edge_id"]} - System ID: {app_info.get("device_sn")}')
    elif "endpoint_id" in app_info:
        log.info(f'Endpoint ID: {app_info["endpoint_id"]}')

    utils.check_license(app_info)

    try:
        edge_data_filename = os.path.join(LOCAL_CONFIG["file-service"]["data_folder"], "edge_data.json")
        edge_data = utils.get_edge_data(app_token)
        if not edge_data:
            log.warning("Fail getting edge_data from cloud")
            exit(1)
        else:
            with open(edge_data_filename, 'w') as fp:
                json.dump(edge_data, fp, default=str)

        if "edge_data" in edge_data:
            log.info(f'EyeflowEdge: {edge_data["edge_data"]["name"]} - {edge_data["edge_data"]["_id"]}')

            if "edge_tasks" in edge_data:
                execute_tasks(app_token, edge_data["edge_tasks"])

            if "flow_name" in edge_data["edge_data"]:
                log.info(f'Running Flow: {edge_data["edge_data"]["flow_name"]} - {edge_data["edge_data"]["flow_id"]} - Last modified: {edge_data["edge_data"]["flow_modified_date"]}')
                flow_id = edge_data["edge_data"]["flow_id"]
                flow_data = edge_client.get_flow(app_token, flow_id)
                if not flow_data:
                    log.error(f"Fail getting flow from local backup. Need to connect to cloud.")
                    exit(1)

                utils.update_components(app_token, flow_data)
                utils.update_models(app_token, flow_data)
        elif "endpoint_data" in edge_data:
            log.info(f'Endpoint: {edge_data["endpoint_data"]["_id"]}')
            flow_id = edge_data["endpoint_data"]["flow_id"]
            flow_data = edge_client.get_flow(app_token, flow_id)
            if not flow_data:
                log.error(f"Fail getting flow from local backup. Need to connect to cloud.")
                exit(1)

            utils.update_components(app_token, flow_data)
            utils.update_models(app_token, flow_data)
        elif "token_data" in edge_data and "endpoint_parms" in edge_data["token_data"]:
            log.info(f'Endpoint: {edge_data["token_data"]["endpoint_id"]}')
            flow_id = edge_data["token_data"]["endpoint_parms"]["flow_id"]
            flow_data = edge_client.get_flow(app_token, flow_id)
            if not flow_data:
                log.error(f"Fail getting flow from local backup. Need to connect to cloud.")
                exit(1)

            utils.update_components(app_token, flow_data)
            utils.update_models(app_token, flow_data)

    except Exception as expt:
        log.error(f'Fail updating edge data {expt}')
        log.error(traceback.format_exc())
        exit(1)
#----------------------------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
