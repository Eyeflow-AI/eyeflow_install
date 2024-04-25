"""
Eyeflow
Manager to start and monitor the endpoint services

Author: Alex Sobral de Freitas
"""

import os
import sys
import traceback
import json
import datetime
import socket
import pika
import time
import subprocess
from subprocess import CalledProcessError
import psutil
from pathlib import Path
import requests
import tarfile
import jwt
import requests

from eyeflow_sdk.message_queue import publish_message
from eyeflow_sdk.log_obj import log

import eyeflow_sdk.nv_gpu as nv_gpu
#----------------------------------------------------------------------------------------------------------------------------------

def update_endpoint(request_parms, body):

    endpoint_token = request_parms["endpoint_token"]
    public_key = request_parms["pub_key"]
    token_payload = jwt.decode(endpoint_token, public_key, algorithms=["RS256"])
    endpoint_update_url = token_payload["endpoint_parms"]["endpoint_update_url"]

    response = requests.put(endpoint_update_url, json=body)
    if not response.ok:
        log.error(f"Fail updating endpoint: {endpoint_update_url} - {response.text}")
        return {
            "status": "fail",
            "message": f"Fail updating endpoint: {endpoint_update_url} - {response.text}"
        }


def get_host_info():
    host_info = {}

    cpu_freq = psutil.cpu_freq(percpu=False)
    host_info["cpu_info"] = {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "current_freq": cpu_freq.current if cpu_freq else 0,
        "max_freq": cpu_freq.max if cpu_freq else 0
    }

    mem_data = psutil.virtual_memory()
    host_info["memory_info"] = {
        "total": mem_data.total,
        "available": mem_data.available
    }

    host_info["disk_info"] = {
        "mounts": []
    }

    try:
        disk_io = psutil.disk_io_counters(perdisk=False)
        host_info["disk_info"]["io_read_count"] = disk_io.read_count
        host_info["disk_info"]["io_write_count"] = disk_io.write_count
        host_info["disk_info"]["io_read_bytes"] = disk_io.read_bytes
        host_info["disk_info"]["io_write_bytes"] = disk_io.write_bytes
    except:
        pass

    for part in psutil.disk_partitions(all=False):
        if 'cdrom' in part.mountpoint or part.fstype == '':
            # skip cd-rom drives with no disk in it; they may raise
            # ENOENT, pop-up a Windows GUI error for a non-ready
            # partition or just hang.
            continue

        usage = psutil.disk_usage(part.mountpoint)
        dsk = {
            "device": part.device,
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "use": usage.percent,
            "type": part.fstype,
            "mount": part.mountpoint
        }

        host_info["disk_info"]["mounts"].append(dsk)

    host_info["net_info"] = psutil.net_io_counters(pernic=True)

    host_info["temperature_info"] = []
    temp_info = dict(psutil.sensors_temperatures())
    for sensor in temp_info:
        sensor_info = {
            "sensor": sensor,
            "info": []
        }

        for info in temp_info[sensor]:
            sensor_info["info"].append({
                "label": info.label,
                "current": info.current,
                "high": info.high,
                "critical": info.critical
            })

        host_info["temperature_info"].append(sensor_info)

    host_info["host_date"] = datetime.datetime.now()

    return host_info
#----------------------------------------------------------------------------------------------------------------------------------


def endpoint_start(request_parms, port):
    endpoint_id = request_parms["endpoint_id"]
    endpoint_token = request_parms["endpoint_token"]
    pub_key = request_parms["pub_key"]

    services_manager_queue = request_parms.get("services_manager_queue", "services_manager")
    container_image = request_parms.get("container_image", "eyeflowai/eyeflow_endpoint-x86_64:latest")
    container_id = f"endpoint_{endpoint_id}"
    endpoint_base_path = os.path.join(BASE_PATH, endpoint_id)

    log.info(f"Starting endpoint container: {container_id} - id: {endpoint_id} - queue: {services_manager_queue} - container_image: {container_image}")

    try:
        data_path = os.path.join(endpoint_base_path, "data")
        log_path = os.path.join(endpoint_base_path, "log")
        components_path = os.path.join(endpoint_base_path, "components")
        run_path = os.path.join(endpoint_base_path, "run")

        Path(data_path).mkdir(parents=True, exist_ok=True)
        Path(log_path).mkdir(parents=True, exist_ok=True)
        Path(components_path).mkdir(parents=True, exist_ok=True)

        response = requests.get(EDGE_INSTALL_URL, params={"downloadformat": "tar.gz"})
        if not response.ok:
            log.error(f"Fail downloading edge install: {EDGE_INSTALL_URL} - {response.text}")
            update_endpoint(request_parms, {
                "status": "fail",
                "logs": {
                    "error": "endpoint_start_fail",
                    "message": f"Fail executing endpoint: {endpoint_id}. Fail downloading edge install: {EDGE_INSTALL_URL} - {response.text}."
                }
            })

        tar_file_path = os.path.join(endpoint_base_path, EDGE_INSTALL_FILE)
        with open(tar_file_path, mode="wb") as file:
            file.write(response.content)

        Path(run_path).mkdir(parents=True, exist_ok=True)

        file_list = [
            "eyeflow_conf.json",
            "run_endpoint.sh",
            "update_edge.py",
            "update_eyeflow_version.py",
            "upload_extracts.py",
            "utils.py"
        ]
        with tarfile.open(tar_file_path, 'r') as tar:
            for file_name in file_list:
                try:
                    tar.extract(member=file_name, path=run_path)
                except KeyError:
                    raise Exception(f"Warning: File '{file_name}' not found in the tar archive {EDGE_INSTALL_FILE}.")

        os.remove(tar_file_path)

        with open(os.path.join(run_path, "edge.license"), "w") as fp:
            fp.write(endpoint_token)

        with open(os.path.join(run_path, "edge-key.pub"), "w") as fp:
            fp.write(pub_key)

        # eyeflow_edge pack
        if not os.path.exists(os.path.join(run_path, "eyeflow_edge")):
            sys.path.append(run_path)
            import utils

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

            pack_doc, pack_filename = utils.download_pack(endpoint_token, edge_pack, pack_folder=os.path.join(data_path, "tmp"))
            with tarfile.open(pack_filename, 'r') as tar:
                tar.extractall(run_path)

        cmd = [
            "docker",
            "run",
            "--env", f"endpoint_id={endpoint_id}",
            "--env", f'MQ_URL={MQ_URL}',
            "--env", f"SERVICES_MANAGER_QUEUE={services_manager_queue}",
            "--gpus", "all",
            "-p", f"{port}:8001",
            "--volume", f"{log_path}:/opt/eyeflow/log",
            "--volume", f"{data_path}:/opt/eyeflow/data",
            "--volume", f"{components_path}:/opt/eyeflow/components",
            "--volume", f"{run_path}:/opt/eyeflow/run",
            f"--name", container_id,
            "--rm",
            "--detach",
            container_image
        ]

        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            log.error(f"Fail running endpoint: {endpoint_id} - {result.stderr.decode()}")
            update_endpoint(request_parms, {
                "status": "fail",
                "logs": {
                    "error": "endpoint_start_fail",
                    "message": f"Fail running endpoint: {endpoint_id}. Fail starting container: {result.stdout.decode()}."
                }
            })

    except CalledProcessError as excp:
        log.error('Fail running endpoint')
        log.error(excp)
        log.error(excp.stdout.decode())
        log.error(excp.stderr.decode())
        update_endpoint(request_parms, {
            "status": "fail",
            "logs": {
                "error": "endpoint_start_fail",
                "message": f"Fail running endpoint: {endpoint_id}. Fail starting container: {excp.stdout.decode()}."
            }
        })
    except Exception as excp:
        log.error('Fail running endpoint')
        log.error(traceback.format_exc())
        update_endpoint(request_parms, {
            "status": "fail",
            "logs": {
                "error": "endpoint_start_fail",
                "message": f"Fail running endpoint: {endpoint_id}. Fail starting container: {excp}."
            }
        })
#----------------------------------------------------------------------------------------------------------------------------------


def endpoint_kill(request_parms):
    endpoint_id = request_parms["endpoint_id"]
    services_manager_queue = request_parms.get("services_manager_queue", "services_manager")
    container_id = f"endpoint_{endpoint_id}"

    log.info(f"Killing endpoint container {container_id}")

    try:
        cmd = [
            "docker",
            "stop",
            container_id
        ]

        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            log.error(f"Fail stopping container: {container_id} - {result}")
            return {
                "status": "fail",
                "message": f"Fail stopping container: {container_id} - {result}"
            }

        return {
            "status": "success",
            "message": f"Endpoint container killed ID: {container_id}"
        }
    except CalledProcessError as excp:
        log.error('Fail killing container')
        log.error(excp)
        log.error(excp.stdout.decode())
        log.error(excp.stderr.decode())
    except Exception as excp:
        log.error('Fail killing container')
        log.error(traceback.format_exc())
        return {
            "status": "fail",
            "message": f"Fail killing container: {container_id} - {excp}"
        }
#----------------------------------------------------------------------------------------------------------------------------------


def SendHostInfo(request_parms):
    try:
        services_manager_queue = request_parms.get("services_manager_queue", "services_manager")
        message = {
            "operation": "set_host_info",
            "hostname": socket.gethostname(),
            "host_info": get_host_info(),
            "host_type": "endpoint"
        }

        all_gpus = nv_gpu.gpu_info()
        with nv_gpu.nvml_context():
            for idx, gpu in enumerate(all_gpus):
                all_gpus[idx].update(nv_gpu.device_status(int(gpu["index"])))

        message["gpu_info"] = all_gpus
        publish_message(message=message, queue=services_manager_queue)
    except Exception as excp:
        log.error('Fail in consumer loop')
        log.error(traceback.format_exc())
        log.error(str(excp))
#----------------------------------------------------------------------------------------------------------------------------------


def get_available_port():
    conn_list = psutil.net_connections()
    used_ports = [conn.laddr.port for conn in conn_list]
    for port in range(PORT_RANGE[0], PORT_RANGE[1]):
        if port not in used_ports:
            return port
#----------------------------------------------------------------------------------------------------------------------------------


def publish_endpoint(request_parms, port):
    conf_line = f"location /endpoint/{request_parms['endpoint_id']} {{ proxy_pass http://localhost:{port}/; }}\n"
    with open(os.path.join(NGINX_CONF_PATH, request_parms['endpoint_id'] + ".conf"), "w") as fp:
        fp.write(conf_line)

    cmd = [
        "nginx",
        "-s",
        "reload"
    ]
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        log.error(f"Fail reloading NGINX conf: {request_parms['endpoint_id']} - {result}")
        update_endpoint(request_parms, {
            "status": "fail",
            "logs": {
                "error": "endpoint_start_fail",
                "message": f"Fail running endpoint: {request_parms['endpoint_id']}. Fail reloading NGINX conf: {result}."
            }
        })
        return

    update_endpoint(request_parms, {
        "status": "active",
        "endpoint_url": SERVER_URL + f"/endpoint/{request_parms['endpoint_id']}",
    })
#----------------------------------------------------------------------------------------------------------------------------------


def on_request(channel, basic_deliver, properties, body):
    """
    Request callback.
    """
    request_parms = json.loads(body.decode())
    # log.info(f"Endpoint Agent request {request_parms}")

    operation = request_parms.get("operation")
    if operation == "endpoint_start":
        port = get_available_port()
        endpoint_start(request_parms, port)
        publish_endpoint(request_parms, port)
    elif operation == "endpoint_kill":
        endpoint_kill(request_parms)
    elif operation == "get_host_info":
        SendHostInfo(request_parms)
    else:
        log.error(f"Unknown operation {operation}")
#----------------------------------------------------------------------------------------------------------------------------------


def main():
    """
    Start message queue consumer for all queues
    """

    try:
        hostname = socket.gethostname()

        while True:
            try:
                mq_connection = pika.BlockingConnection(pika.URLParameters(MQ_URL))
                mq_channel = mq_connection.channel()

                queue_name = f'endpoint_agent.{hostname}'
                mq_channel.exchange_declare(exchange=SERVICES_MANAGER_BROADCAST_QUEUE, exchange_type='fanout')
                mq_channel.queue_declare(queue=queue_name, exclusive=True)
                mq_channel.queue_bind(exchange=SERVICES_MANAGER_BROADCAST_QUEUE, queue=queue_name)
                mq_channel.basic_qos(prefetch_count=1)
                mq_channel.basic_consume(queue=queue_name, on_message_callback=on_request, auto_ack=True)

                # SendHostInfo({"services_manager_queue": SERVICES_MANAGER_QUEUE})

                log.info(f"EndpointAgent Awaiting requests Queue: {queue_name}")
                mq_channel.start_consuming()
            except Exception as excp:
                log.error('Fail in consumer loop')
                log.error(str(excp))
                time.sleep(5)
                if mq_channel.is_open:
                    mq_channel.close()
                if mq_connection.is_open:
                    mq_connection.close()
                log.info('Retry connect')
    except Exception as excp:
        log.error('Fail starting service')
        log.error(str(excp))
#----------------------------------------------------------------------------------------------------------------------------------

BASE_PATH = "/opt/endpoint"
EDGE_INSTALL_URL = "https://eyeflow.ai/static/media/edge_install.tar.gz"
EDGE_INSTALL_FILE = "edge_install.tar.gz"
MQ_URL = os.environ.get("MQ_URL", "amqp://eyeflow_app:G4r6DxUdC8g5u85Q@rabbitmq.eyeflow.ai:5672")
SERVICES_MANAGER_QUEUE = os.environ.get("SERVICES_MANAGER_QUEUE", "services_manager") # "services_manager_dev"
SERVICES_MANAGER_BROADCAST_QUEUE = os.environ.get("SERVICES_MANAGER_BROADCAST_QUEUE", "services_manager_broadcast") # "services_manager_broadcast_dev"
PORT_RANGE = [8100, 8150]
SERVER_URL = os.environ.get("SERVER_URL", "https://endpoint-1.eyeflow.ai")
NGINX_CONF_PATH = "/etc/nginx/api_conf.d/"

main()
