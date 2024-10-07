#!/usr/bin/python3

import os
import sys
import time
import json
import utils
import requests
import argparse
# from bson import ObjectId
from eyeflow_sdk.log_obj import CONFIG

proxies = {}
if "proxies" in CONFIG:
    proxies = CONFIG["proxies"]
#----------------------------------------------------------------------------------------------------------------------------------

def parse_args(args):
    """ Parse the arguments.
    """
    parser = argparse.ArgumentParser(prog='request_license', description='Eyeflow Request License')
    parser.add_argument('edge', help='The ID/Name of edge device', type=str)
    parser.add_argument('environment', help='The ID/Name of client environment', type=str)
    parser.add_argument('--out_file', '-o', dest='out_file', help='The json file to save device info', type=str, action='store', default='license.json')

    return parser.parse_args(args)
#----------------------------------------------------------------------------------------------------------------------------------

def main(args=None):
    # parse arguments
    if os.environ.get('EDGE_ENVIRONMENT') is not None:
        environment = os.environ.get('EDGE_ENVIRONMENT')
        edge = os.environ.get('EDGE_DEVICE')
        out_file = 'license.json'
    elif args is None and len(sys.argv) < 3:
        environment = input("Enter the name of the Environment: ")
        edge = input("Enter the name of the Edge device: ")
        out_file = 'license.json'
    elif len(sys.argv) == 3:
        args = sys.argv[1:]

    if args is not None:
        args = parse_args(args)
        environment = args.environment
        edge = args.edge
        out_file = args.out_file

    device_info = utils.get_device_info()

    device_info["edge_id"] = edge
    device_info["environment_id"] = environment
    device_info["device_sn"] = device_info.get('device_sn') or None

    with open(out_file, 'w') as fp:
        json.dump(device_info, fp, default=str, ensure_ascii=False)

    # Start validation process
    validated = False
    response = requests.post(f"{CONFIG['ws']}/edge/activate/", data=device_info, proxies=proxies)
    if (response.json().get('payload')):
        validation_code = response.json()['payload']['validation_code']
        print('Enter this code on the device at Eyeflow App https://app.eyeflow.ai/app/devices')
        print(f'{validation_code}')
        checking_info = {
            "edge_id": device_info["edge_id"],
            "environment_id": device_info["environment_id"],
            "validation_code": validation_code,
        }

        print("Waiting validation on Eyeflow App ", end="", flush=True)
        while not validated:
            print('.', end="", flush=True)
            get_response = requests.get(f"{CONFIG['ws']}/edge/check-validation/?edge_id={checking_info['edge_id']}&environment_id={checking_info['environment_id']}&validation_code={checking_info['validation_code']}", proxies=proxies)
            if (get_response.json().get('ok') == True):
                with open(os.path.join(CONFIG["file-service"]["run_folder"], 'edge.license'), 'w') as _license:
                    _license.write(get_response.json()['info']['token'])
                with open(os.path.join(CONFIG["file-service"]["run_folder"], 'edge-key.pub'), 'w') as _pub:
                    _pub.write(get_response.json()['info']['public_key'])
                validated = True
                print('Validated!')
            else:
                time.sleep(5)
    else:
        print(response.json()['error']['message'])
#----------------------------------------------------------------------------------------------------------------------------------

main()
