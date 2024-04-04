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
import subprocess
import datetime

conf_path = os.path.join(os.path.dirname(__file__), "eyeflow_conf.json")
if not os.path.exists(conf_path):
    conf_path = "/opt/eyeflow/run/eyeflow_conf.json"

if not os.path.exists(conf_path):
    print("Error: eyeflow_conf.json not found")
    sys.exit(1)

with open(conf_path) as fp:
    LOCAL_CONFIG = json.load(fp)

from eyeflow_sdk.log_obj import log
import utils
#----------------------------------------------------------------------------------------------------------------------------------

def process_status(process_name):
    try:
        subprocess.check_output(["pgrep", process_name])
        return True
    except subprocess.CalledProcessError:
        return False
#----------------------------------------------------------------------------------------------------------------------------------


def check_eyeflow_version(app_token):
    pack_id = "64fb7933f257ab6cb37ce65d"
    pack_name = "eyeflow_edge"
    edge_pack = {
        "name": pack_name,
        "id": pack_id,
        "version": "latest"
    }

    lib_pack = {
        "name": "edge_sdk_libs",
        "id": "65a987e1e90f2032a3886890",
        "version": "latest"
    }

    def install_edge():
        # pack_doc, pack_filename = utils.download_pack(app_token, lib_pack, pack_folder=LOCAL_CONFIG["file-service"]["temp_folder"])
        # retcode, stdout, stderr = utils.install_pack(pack_doc, pack_filename)

        pack_doc, pack_filename = utils.download_pack(app_token, edge_pack, pack_folder=LOCAL_CONFIG["file-service"]["temp_folder"])
        run_status = process_status("eyeflow_edge")
        if run_status:
            log.info("Stoping edge to update")
            ret = subprocess.run(os.path.join(os.path.dirname(__file__), "stop_edge"), shell=True, capture_output=True)
            if ret.returncode != 0:
                log.error(f"Fail in Stop edge - result: {ret.returncode}, {ret.stdout.decode()}, {ret.stderr.decode()}")
                # raise Exception(f"Fail installing eyeflow_edge: {ret.stdout.decode()} - {ret.stderr.decode()}")

        try:
            retcode, stdout, stderr = utils.install_pack(pack_doc, pack_filename)
        except:
            pass

        if run_status:
            log.info("Starting edge")
            ret = subprocess.run(os.path.join(os.path.dirname(__file__), "start_edge"), shell=True, capture_output=True)
            if ret.returncode != 0:
                log.error(f"Fail in Start edge - result: {ret.returncode}, {ret.stdout.decode()}, {ret.stderr.decode()}")
                raise Exception(f"Fail installing eyeflow_edge: {ret.stdout.decode()} - {ret.stderr.decode()}")

            if retcode != 0:
                raise Exception(f"Fail installing eyeflow_edge: {stdout} - {stderr}")

    if not os.path.isfile(os.path.join(LOCAL_CONFIG["file-service"]["run_folder"], "eyeflow_edge")):
        install_edge()
        return

    if not os.path.isfile(os.path.join(LOCAL_CONFIG["file-service"]["run_folder"], "manifest.json")):
        install_edge()
        return

    with open(os.path.join(LOCAL_CONFIG["file-service"]["run_folder"], "manifest.json")) as fp:
        manifest = json.load(fp)

    pack_cloud_doc = None
    try:
        pack_cloud_doc = utils.get_pack(app_token, {"name": pack_name, "id": pack_id})
    except:
        pass

    if pack_cloud_doc is not None:
        if datetime.datetime.strptime(pack_cloud_doc["filedate"], "%Y-%m-%dT%H:%M:%S.%f%z") > datetime.datetime.fromisoformat(manifest["compilation_date"]):
            edge_pack["version"] = pack_cloud_doc["version"]
            install_edge()
#----------------------------------------------------------------------------------------------------------------------------------

app_info, app_token = utils.get_license()
log.info(f'Edge ID: {app_info["edge_id"]} - System ID: {app_info.get("device_sn")}')
utils.check_license(app_info)
check_eyeflow_version(app_token)
