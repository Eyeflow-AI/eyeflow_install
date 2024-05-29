import os
import sys
import platform
import socket
import uuid
import json
import jwt
import requests
import datetime
import shutil
import subprocess
import tarfile
from pathlib import Path

from eyeflow_sdk.log_obj import log
from eyeflow_sdk import jetson_utils
from eyeflow_sdk import edge_client

os.environ["CUDA_MODULE_LOADING"] = "LAZY"

conf_path = "/opt/eyeflow/run/eyeflow_conf.json"
if not os.path.exists(conf_path):
    conf_path = os.path.join(os.path.dirname(__file__), "eyeflow_conf.json")

if not os.path.exists(conf_path):
    print("Error: eyeflow_conf.json not found")
    sys.exit(1)

with open(conf_path) as fp:
    LOCAL_CONFIG = json.load(fp)
#----------------------------------------------------------------------------------------------------------------------------------


def download_file(url, local_filename):
    os.makedirs(os.path.dirname(local_filename), exist_ok=True)
    with requests.get(url, stream=True) as r:
        r.raise_for_status()

        if os.path.isfile(local_filename):
            os.remove(local_filename)

        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                # If you have chunk encoded response uncomment 'if' and set chunk_size parameter to None.
                #if chunk:
                f.write(chunk)
# ---------------------------------------------------------------------------------------------------------------------------------


def download_pack(app_token, pack, pack_folder):
    try:
        arch = get_device_arch()
        log.info(f'Download pack {pack["name"]}-{arch}')

        folder_path = Path(pack_folder)
        if not folder_path.is_dir():
            folder_path.mkdir(parents=True, exist_ok=True)

        endpoint = jwt.decode(app_token, options={"verify_signature": False})['endpoint']
        url = f'{endpoint}/pack/{pack["id"]}/arch/{arch}/?version={pack["version"]}'
        msg_headers = {'Authorization' : f'Bearer {app_token}'}
        payload = {"download_url": True}
        response = requests.get(url, headers=msg_headers, params=payload)

        if response.status_code != 200:
            log.error(f'Failing downloading pack {pack["name"]}: {response.json()}')
            return None, None

        pack_doc = response.json()
        dest_filename = os.path.join(folder_path, pack_doc["filename"])
        download_file(pack_doc["download_url"], dest_filename)
        return pack_doc, dest_filename

    except requests.ConnectionError as error:
        log.error(f'Failing downloading pack: {pack["name"]}. Connection error: {error}')
        return None, None
    except requests.Timeout as error:
        log.error(f'Failing downloading pack: {pack["name"]}. Timeout: {error}')
        return None, None
    except Exception as excp:
        log.error(f'Failing downloading pack: {pack["name"]} - {excp}')
        return None, None
# ---------------------------------------------------------------------------------------------------------------------------------


def get_pack(app_token, pack):
    try:
        arch = get_device_arch()
        # log.info(f'Get pack {pack["name"]}-{arch}')

        endpoint = jwt.decode(app_token, options={"verify_signature": False})['endpoint']
        url = f'{endpoint}/pack/{pack["id"]}/arch/{arch}/'
        msg_headers = {'Authorization' : f'Bearer {app_token}'}
        payload = {"download_url": False}
        response = requests.get(url, headers=msg_headers, params=payload)

        if response.status_code != 200:
            log.error(f'Failing in get pack {pack["name"]}: {response.json()}')
            return None

        return response.json()

    except requests.ConnectionError as error:
        log.error(f'Failing in get pack: {pack["name"]}. Connection error: {error}')
        return None
    except requests.Timeout as error:
        log.error(f'Failing in get pack: {pack["name"]}. Timeout: {error}')
        return None
    except Exception as excp:
        log.error(f'Failing in get pack: {pack["name"]} - {excp}')
        return None
# ---------------------------------------------------------------------------------------------------------------------------------


def install_pack(pack_doc, filename):
    try:
        log.info(f'Installing pack {pack_doc["pack_name"]} - version: {pack_doc["version"]}')

        pack_folder = os.path.join(os.path.dirname(filename), pack_doc["pack_name"])
        if os.path.isdir(pack_folder):
            shutil.rmtree(pack_folder)

        with tarfile.open(filename, 'r') as tar:
            tar.extractall(pack_folder)

        setup_script = os.path.join(pack_folder, "setup.sh")
        if not os.path.isfile(setup_script):
            raise Exception(f"Pack does not have a setup script: {setup_script}")

        ret = subprocess.run(f"cd {pack_folder} && sh setup.sh", capture_output=True, shell=True)
        # log.info(f"Setup result: {ret.returncode}, {ret.stdout.decode()}, {ret.stderr.decode()}")
        if ret.returncode != 0:
            err = f"Pack install fail: {ret.returncode}, {ret.stdout.decode()}, {ret.stderr.decode()}"
            log.error(err)

        return ret.returncode, ret.stdout.decode(), ret.stderr.decode()
    except Exception as excp:
        err = f'Failing installing pack: {pack_doc["pack_name"]} - {excp}'
        log.error(err)
        return 1, "", err
# ---------------------------------------------------------------------------------------------------------------------------------


def get_model(app_token, dataset_id, model_folder, model_type="tensorflow"):
    local_doc = None
    try:
        # log.info(f"Check model {dataset_id}")

        local_cache = os.path.join(model_folder, dataset_id + '.json')
        if os.path.isfile(local_cache):
            with open(local_cache) as fp:
                local_doc = json.load(fp)

        endpoint = jwt.decode(app_token, options={"verify_signature": False})['endpoint']
        url = f"{endpoint}/published-model-v2/{dataset_id}/"
        msg_headers = {'Authorization' : f'Bearer {app_token}'}
        payload = {"download_url": False}
        response = requests.get(url, headers=msg_headers, params=payload)

        if response.status_code != 200:
            if local_doc:
                return local_doc

            log.error(f"Failing get model: {url} - {response.json()}")
            return None

        model_doc = response.json()
        if local_doc and model_doc["date"] == local_doc["date"]:
            return local_doc

        payload = {"download_url": True}
        response = requests.get(url, headers=msg_headers, params=payload)

        if response.status_code != 200:
            if local_doc:
                return local_doc

            log.error(f"Failing get model: {response.json()}")
            return None

        model_doc = response.json()

        if "model_list" not in model_doc:
            log.error(f"Get model response dont have model_list key: {model_doc}")
            raise Exception(f"Get model response dont have model_list key: {model_doc}")

        if len(model_doc["model_list"]):
            for model_data in model_doc["model_list"]:
                if model_data.get("type", "") == model_type:
                    download_url = model_data["download_url"]
                    dest_filename = os.path.join(model_folder, model_data["file"])
                    break
            else:
                log.warning(f"Did not find model type {model_type} in {dataset_id} document - {model_doc}")
                return model_doc
        else:
            log.warning(f"Model list is empty for dataset {dataset_id}")
            with open(local_cache, 'w') as fp:
                json.dump(model_doc, fp, default=str)
            return model_doc

        log.info(f"Download model {dataset_id} - Train date: {model_doc['date']}")
        download_file(download_url, dest_filename)

        # expand_file
        if (dest_filename.endswith('tar.gz')):
            if model_type == "onnx":
                folder_path = Path(model_folder)
            else:
                folder_path = Path(model_folder + '/' + dataset_id)

            if not folder_path.is_dir():
                folder_path.mkdir(parents=True, exist_ok=True)

            with tarfile.open(dest_filename, 'r') as tar:
                tar.extractall(folder_path)

            os.remove(dest_filename)

        if os.path.isfile(local_cache):
            os.remove(local_cache)

        with open(local_cache, 'w') as fp:
            json.dump(model_doc, fp, default=str)

        return model_doc

    except requests.ConnectionError as error:
        if local_doc:
            return local_doc

        log.error(f'Failing get model dataset_id: {dataset_id}. Connection error: {error}')
        return None
    except requests.Timeout as error:
        if local_doc:
            return local_doc

        log.error(f'Failing get model dataset_id: {dataset_id}. Timeout: {error}')
        return None
    except Exception as excp:
        log.error(f'Failing get model dataset_id: {dataset_id} - {excp}')
        return None
# ---------------------------------------------------------------------------------------------------------------------------------


def update_models(app_token, flow_data):
    """
    Update models for processing flow
    """

    # log.info(f"Update models for flow")

    datasets_downloaded = []
    for comp in flow_data["nodes"]:
        if "dataset_id" in comp["options"]:
            dataset_id = comp["options"]["dataset_id"]
            if dataset_id not in datasets_downloaded:
                datasets_downloaded.append(dataset_id)
                model_folder = LOCAL_CONFIG["file-service"]["model"]
                model_file = os.path.join(model_folder, dataset_id + ".onnx")
                info_file = os.path.join(model_folder, dataset_id + ".json")
                if os.path.isfile(info_file) and not os.path.isfile(model_file):
                    os.remove(info_file)

                model_doc = get_model(app_token, dataset_id, model_folder=model_folder, model_type="onnx")
                if "model_list" in model_doc and len(model_doc["model_list"]) == 0:
                    log.warning(f"Empty model for dataset {dataset_id}")
                    continue

                if not os.path.isfile(model_file):
                    raise Exception(f'Model for dataset {dataset_id} not found at: {model_file}')
#----------------------------------------------------------------------------------------------------------------------------------


def upload_flow_extracts(app_token, flow_data, max_examples=400):
    """
    Upload extracts to datasets after processing video
    """

    log.info(f"Upload extracts for flow")

    datasets_uploaded = []
    for comp in flow_data["nodes"]:
        if "dataset_id" in comp["options"] and comp["options"]["dataset_id"] not in datasets_uploaded:
            dataset_id = comp["options"]["dataset_id"]
            datasets_uploaded.append(dataset_id)
            extract_path = os.path.join(LOCAL_CONFIG["file-service"]["extract"], dataset_id)
            files_uploaded = os.listdir(extract_path)
            if not edge_client.upload_extract(
                app_token,
                dataset_id,
                extract_folder=LOCAL_CONFIG["file-service"]["extract"],
                max_files=max_examples,
                thumb_size=128
            ):
                log.error(f'Fail uploading extract {dataset_id}')

            log.info("Deleting files from: " + extract_path)
            for filename in files_uploaded:
                try:
                    os.remove(os.path.join(extract_path, filename))
                except:
                    pass
#----------------------------------------------------------------------------------------------------------------------------------


def get_license(filename="edge.license"):
    # read app_token
    license_file = os.path.join(LOCAL_CONFIG["file-service"]["run_folder"], filename)
    if not os.path.isfile(license_file):
        log.error(f'Error: license_file not found {license_file}')
        raise Exception(f'Error: license_file not found {license_file}')

    with open(license_file, 'r') as fp:
        app_token = fp.read()

    key_file = os.path.join(LOCAL_CONFIG["file-service"]["run_folder"], "edge-key.pub")
    if not os.path.isfile(key_file):
        log.error(f'Error: token pub key not found {key_file}')
        raise Exception(f'Error: token pub key not found {key_file}')

    with open(key_file) as fp:
        public_key = fp.read()

    app_info = jwt.decode(app_token, public_key, algorithms=['RS256'])
    return app_info, app_token
#----------------------------------------------------------------------------------------------------------------------------------


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP
#----------------------------------------------------------------------------------------------------------------------------------


def get_device_sn():
    try:
        filename = "/sys/class/dmi/id/product_uuid"
        if os.path.isfile(filename):
            with open(filename, 'r') as fp:
                device_id = fp.readline()

            return device_id.rstrip()
    except:
        return None
#----------------------------------------------------------------------------------------------------------------------------------


def get_device_info():
    plat_info = platform.platform().split('-')
    if plat_info[0] != "Linux":
        raise Exception(f"Invalid platform: {plat_info[0]}")

    if "aarch64" in plat_info:
        idx = plat_info.index("aarch64")
        device_arch = f"{plat_info[idx - 1]}-{plat_info[idx]}"
        device_sn = jetson_utils.get_jetson_module_sn()
    elif "x86_64" in plat_info:
        idx = plat_info.index("x86_64")
        device_arch = f"{plat_info[idx - 1]}-{plat_info[idx]}"
        device_sn = get_device_sn()
    # 'WSL2-x86_64'
    else:
        raise Exception(f"Invalid device_architecture: {'-'.join(plat_info)}")

    sys_info = {
        "hostname": socket.gethostname(),
        "ip": get_ip(),
        "device_sn": device_sn,
        "device_architecture": device_arch
    }

    node_id = uuid.getnode()
    if node_id == uuid.getnode():
        sys_info["node_id"] = node_id

    return sys_info
#----------------------------------------------------------------------------------------------------------------------------------


def get_device_arch():
    plat_info = platform.platform().split('-')
    if plat_info[0] != "Linux":
        raise Exception(f"Invalid platform: {plat_info[0]}")

    if "aarch64" in plat_info:
        idx = plat_info.index("aarch64")
        return f"{plat_info[idx]}"
    elif "x86_64" in plat_info:
        idx = plat_info.index("x86_64")
        return f"{plat_info[idx]}"
#----------------------------------------------------------------------------------------------------------------------------------


def check_license(license_info):
    device_info = get_device_info()
    # if license_info.get("hostname"):
    #     if device_info["hostname"] != license_info["hostname"]:
    #         raise Exception("Invalid license for device")

    # if license_info.get("ip"):
    #     if device_info["ip"] != license_info["ip"]:
    #         raise Exception("Invalid license for device")

    # if license_info.get("device_architecture"):
    #     if device_info["device_architecture"] != license_info["device_architecture"]:
    #         raise Exception("Invalid license for device")

    if license_info.get("device_sn"):
        if device_info["device_sn"] != license_info["device_sn"]:
            if device_info["device_architecture"] == "generic-x86_64" and not device_info["device_sn"]:
                log.warning("Must run as root")
            else:
                raise Exception("Invalid license for device")

    # if license_info.get("node_id"):
    #     if device_info["node_id"] != license_info["node_id"]:
    #         log.warning("Invalid node_id")
            # raise Exception("Invalid license for device")
#----------------------------------------------------------------------------------------------------------------------------------


def get_edge_data(app_token):
    try:
        log.info(f"Get edge_data")
        endpoint = jwt.decode(app_token, options={"verify_signature": False})['endpoint']
        msg_headers = {'Authorization' : f'Bearer {app_token}'}
        response = requests.get(f"{endpoint}", headers=msg_headers)

        if response.status_code != 200:
            log.error(f"Failing get edge_data: {response.json()}")
            return None

        return response.json()

    except requests.ConnectionError as error:
        log.error(f'Failing get edge_data. Connection error: {error}')
        return None
    except requests.Timeout as error:
        log.error(f'Failing get edge_data. Timeout: {error}')
        return None
    except Exception as excp:
        log.error(f'Failing get edge_data - {excp}')
        return None
#----------------------------------------------------------------------------------------------------------------------------------
