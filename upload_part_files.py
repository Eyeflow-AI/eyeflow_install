#!/usr/bin/python3
import os
import sys
import json
import argparse
import tarfile

from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from eyeflow_sdk.log_obj import log, CONFIG

import utils
# ---------------------------------------------------------------------------------------------------------------------

proxies = {}
if "proxies" in CONFIG:
    proxies = CONFIG["proxies"]

if "storage_credentials" not in CONFIG:
    log.error("Storage credentials not found in the configuration.")
    exit(1)
# ---------------------------------------------------------------------------------------------------------------------

def upload_files_part(folder, date, part):
    try:
        base_folder = "/opt/eyeflow/data/"
        src_folder = os.path.join(base_folder, folder, date)
        tar_filename = f"/tmp/{part}.tar.gz"
        if os.path.isfile(tar_filename):
            os.remove(tar_filename)

        with tarfile.open(tar_filename, "w:gz") as tar:
            wd = os.getcwd()
            os.chdir(src_folder)
            for filename in os.listdir():
                if f"_{part}" in filename:
                    tar.add(os.path.basename(filename))

            os.chdir(wd)

        with open(tar_filename, 'rb') as file:
            data = file.read()

        blob_client = BlobServiceClient(
            account_url=CONFIG["storage_credentials"]["account_url"],
            credential=CONFIG["storage_credentials"]["account_key"],
            proxies=proxies
        )

        blob_name = f"{edge_name}/{os.path.basename(tar_filename)}"
        upload_blob = blob_client.get_blob_client(container='edge-upload', blob=blob_name)
        upload_blob.upload_blob(data=bytes(data))

        log.info(f"File {blob_name} uploaded successfully.")

    except ResourceExistsError as e:
        log.error(f"Resource already exists: {e}")
    except ResourceNotFoundError as e:
        log.error(f"Resource not found: {e}")
    except Exception as e:
        log.error(f"An error occurred: {e}")
# ---------------------------------------------------------------------------------------------------------------------


parser = argparse.ArgumentParser(description='Copy parts files')
parser.add_argument('date', help='A data', type=str)
parser.add_argument('parts_list', help='A lista de ids separada por virgula', type=str)

with open('/opt/eyeflow/data/edge_data.json', 'r') as f:
    edge_data = json.load(f)

edge_name = edge_data["edge_data"]["name"]

args = parser.parse_args(sys.argv[1:])
part_list = args.parts_list.split(',')
for part in part_list:
    upload_files_part("video", args.date, part)
