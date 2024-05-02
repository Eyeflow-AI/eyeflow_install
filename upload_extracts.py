#!/usr/bin/python3

"""
SiliconLife Eyeflow
Function to upload flow extracts at edge

Author: Alex Sobral de Freitas
"""

import os
import traceback
import sys
import argparse
import json
from eyeflow_sdk import edge_client

os.environ["CONF_PATH"] = os.path.dirname(__file__)

with open(os.path.join(os.path.dirname(__file__), "../run/", "eyeflow_conf.json")) as fp:
    LOCAL_CONFIG = json.load(fp)

from eyeflow_sdk.log_obj import log
import utils
#----------------------------------------------------------------------------------------------------------------------------------

def get_dataset_folder(dataset):
    dataset_folder = os.path.join(LOCAL_CONFIG["file-service"]["extract"], dataset)
    if os.path.isdir(dataset_folder):
        return dataset_folder, dataset

    for dset in os.listdir(LOCAL_CONFIG["file-service"]["model"]):
        dataset_folder = os.path.join(LOCAL_CONFIG["file-service"]["model"], dset)
        if os.path.isfile(os.path.join(dataset_folder, dset + ".json")):
            with open(os.path.join(dataset_folder, dset + ".json")) as fp:
                dset_data = json.load(fp)

            if dset_data["name"] == dataset or dset_data["info"]["long_name"] == dataset:
                dataset_folder = os.path.join(LOCAL_CONFIG["file-service"]["extract"], dset_data["_id"])
                if os.path.isdir(dataset_folder):
                    return dataset_folder, dset_data["_id"]

    raise Exception(f"Dataset not found: {dataset}")
#----------------------------------------------------------------------------------------------------------------------------------

def parse_args(args):
    """ Parse the arguments.
    """
    parser = argparse.ArgumentParser(description='Upload flow extracts.')
    parser.add_argument('-d', '--dataset', help='The ID/Name of dataset to upload', type=str)

    return parser.parse_args(args)
#----------------------------------------------------------------------------------------------------------------------------------

def main(args=None):
    # parse arguments
    if args is None:
        args = sys.argv[1:]

    args = parse_args(args)
    log.info("args: {}".format(args))

    app_info, app_token = utils.get_license()

    if "endpoint_id" in app_info:
        log.info(f'Endpoint ID: {app_info["endpoint_id"]}')
        host_type = "endpoint"
    elif "edge_id" in app_info:
        log.info(f'Edge ID: {app_info["edge_id"]} - System ID: {app_info.get("device_sn")}')
        host_type = "edge"
    else:
        log.error(f'No endpoint_id or edge_id found in license')
        exit(1)

    utils.check_license(app_info)

    if args.dataset:
        extract_path, dataset_id = get_dataset_folder(args.dataset)
        files_uploaded = os.listdir(extract_path)
        if not edge_client.upload_extract(
            app_token,
            dataset_id,
            extract_folder=LOCAL_CONFIG["file-service"]["extract"],
            max_files=800,
            thumb_size=128
        ):
            log.error(f'Fail uploading extract {args.dataset}')
        else:
            log.info("Deleting files from: " + extract_path)
            for filename in files_uploaded:
                try:
                    os.remove(os.path.join(extract_path, filename))
                except:
                    pass
    else:
        try:
            if host_type == "endpoint":
                with open("/opt/eyeflow/data/edge_data.json", "r") as fp:
                    edge_data = json.load(fp)
                token_data = edge_data["token_data"]
                flow_id = token_data["flow_id"]
                with open(f"/opt/eyeflow/data/flow/{flow_id}.json", "r") as fp:
                    flow_data = json.load(fp)
            else:
                edge_data = edge_client.get_edge_data(app_token)
                if not edge_data:
                    raise Exception("Fail getting edge_data")

                log.info(edge_data)
                flow_id = edge_data["flow_id"]

                flow_data = edge_client.get_flow(app_token, flow_id)

            utils.upload_flow_extracts(app_token, flow_data)

        except Exception as expt:
            log.error(f'Fail processing flow')
            log.error(traceback.format_exc())
            return

#----------------------------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    # main(["-d", "62ab2e74fa4fd9001b311b1d"])
    # main(["-d", "Surface Defects"])
    main()
