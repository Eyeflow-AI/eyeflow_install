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
from eyeflow_sdk.log_obj import CONFIG, log

from eyeflow_sdk.dataset_utils import Dataset

proxies = {}
if "proxies" in CONFIG:
    proxies = CONFIG["proxies"]

import utils
#----------------------------------------------------------------------------------------------------------------------------------

def get_dataset_folder(dataset):
    dataset_folder = os.path.join(CONFIG["file-service"]["extract"], dataset)
    if os.path.isdir(dataset_folder):
        return dataset_folder, dataset

    for dset in os.listdir(CONFIG["file-service"]["model"]):
        dataset_folder = os.path.join(CONFIG["file-service"]["model"], dset)
        if os.path.isfile(os.path.join(dataset_folder, dset + ".json")):
            with open(os.path.join(dataset_folder, dset + ".json")) as fp:
                dset_data = json.load(fp)

            if dset_data["name"] == dataset or dset_data["info"]["long_name"] == dataset:
                dataset_folder = os.path.join(CONFIG["file-service"]["extract"], dset_data["_id"])
                if os.path.isdir(dataset_folder):
                    return dataset_folder, dset_data["_id"]

    raise Exception(f"Dataset not found: {dataset}")
#----------------------------------------------------------------------------------------------------------------------------------

def parse_args(args):
    """ Parse the arguments.
    """
    parser = argparse.ArgumentParser(description='Upload flow extracts.')
    parser.add_argument('-d', '--dataset', help='The ID/Name of dataset to upload', type=str)
    parser.add_argument('-dd', '--ddataset', help='The ID/Name of dataset destination to upload from source dataset', type=str)

    return parser.parse_args(args)
#----------------------------------------------------------------------------------------------------------------------------------


def map_and_update_extract_classes(args, app_token):
    """
    Copy all extracts from source dataset to destination dataset,
    modifying class labels in _data.json files to match destination dataset.
    """
    source_dataset = Dataset(args.dataset, app_token)
    source_dataset.load_data()

    destination_dataset = Dataset(args.ddataset, app_token)
    destination_dataset.load_data()

    extract_path, dataset_id = get_dataset_folder(args.dataset)
    os.makedirs(os.path.join(CONFIG["file-service"]["extract"], args.ddataset), exist_ok=True)
    destination_extract_path = os.path.join(CONFIG["file-service"]["extract"], args.ddataset)
    
    log.info(f"Copying extracts from {extract_path} to {destination_extract_path}")

    destination_parms = destination_dataset.parms.get("classes", [])
    extracts = os.listdir(extract_path)
    
    files_processed = 0
    files_modified = 0

    for extract in extracts:
        source_file_path = os.path.join(extract_path, extract)
        destination_file_path = os.path.join(destination_extract_path, extract)

        try:
            if extract.endswith("_data.json"):
                # Process and modify _data.json files
                with open(source_file_path, 'r') as f:
                    extract_data = json.load(f)
                
                if "annotations" in extract_data and "instances" in extract_data["annotations"]:
                    for instance in extract_data["annotations"]["instances"]:
                        for parms in destination_parms:
                            if instance.get("label") == parms.get("label"):
                                instance["class"] = parms["name"]
                
                with open(destination_file_path, 'w') as f:
                    json.dump(extract_data, f, indent=4)
                
                files_modified += 1
                log.info(f"Modified and saved: {extract}")
                
            else:
                # Copy other files as-is (images, thumbnails, etc.)
                if os.path.isfile(source_file_path):
                    import shutil
                    shutil.copy2(source_file_path, destination_file_path)
                    log.debug(f"Copied: {extract}")
            
            files_processed += 1

        except Exception as e:
            log.error(f"Error processing {extract}: {e}")

    log.info(f"Completed: {files_processed} files processed, {files_modified} JSON files modified")
    log.info(f"Source classes: {source_dataset.parms.get('classes', [])}")
    log.info(f"Destination classes: {destination_dataset.parms.get('classes', [])}")


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
        source_extract_path, source_dataset_id = get_dataset_folder(args.dataset)
        target_dataset_id = source_dataset_id
        target_extract_path = source_extract_path

        if args.ddataset:
            log.info("Mapping and updating extracts for destination dataset.")
            map_and_update_extract_classes(args, app_token)
            target_dataset_id = args.ddataset
            target_extract_path = os.path.join(CONFIG["file-service"]["extract"], args.ddataset)
        else:
            log.info("Source and destination datasets are the same.")

        files_to_upload_and_delete = os.listdir(target_extract_path)
        if not edge_client.upload_extract(
            app_token,
            target_dataset_id,
            extract_folder=CONFIG["file-service"]["extract"],
            max_files=800,
            thumb_size=128
        ):
            log.error(f'Fail uploading extract {target_dataset_id}')
        else:
            log.info("Deleting files from: " + target_extract_path)
            for filename in files_to_upload_and_delete:
                try:
                    os.remove(os.path.join(target_extract_path, filename))
                except Exception as e:
                    log.error(f"Error deleting file {filename}: {e}")
    else:
        try:
            if host_type == "endpoint":
                with open("/opt/eyeflow/data/edge_data.json", "r") as fp:
                    edge_data = json.load(fp)
                token_data = edge_data["token_data"]
                flow_id = token_data["endpoint_parms"]["flow_id"]
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
    main()
