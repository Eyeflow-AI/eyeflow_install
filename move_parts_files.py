#!/usr/bin/python3
import os
from pymongo.mongo_client import MongoClient
import datetime
import json
import tarfile
import jwt
import requests

from eyeflow_sdk.log_obj import log, CONFIG
# ---------------------------------------------------------------------------------------------------------------------

proxies = {}
if "proxies" in CONFIG:
    proxies = CONFIG["proxies"]
# ---------------------------------------------------------------------------------------------------------------------

def get_license(filename="edge.license"):
    # read app_token
    license_file = os.path.join(CONFIG["file-service"]["run_folder"], filename)
    if not os.path.isfile(license_file):
        log.error(f'Error: license_file not found {license_file}')
        raise Exception(f'Error: license_file not found {license_file}')

    with open(license_file, 'r') as fp:
        app_token = fp.read()

    key_file = os.path.join(CONFIG["file-service"]["run_folder"], "edge-key.pub")
    if not os.path.isfile(key_file):
        log.error(f'Error: token pub key not found {key_file}')
        raise Exception(f'Error: token pub key not found {key_file}')

    with open(key_file) as fp:
        public_key = fp.read()

    app_info = jwt.decode(app_token, public_key, algorithms=['RS256'])
    return app_info, app_token
#----------------------------------------------------------------------------------------------------------------------------------

def upload_files_part(app_token, app_info, folder, date, part):
    try:
        src_folder = os.path.join(CONFIG["file-service"]["data_folder"], folder, date)
        tar_filename = f"/tmp/{part}.tar.gz"
        if os.path.isfile(tar_filename):
            os.remove(tar_filename)

        count_files = 0
        with tarfile.open(tar_filename, "w:gz") as tar:
            wd = os.getcwd()
            os.chdir(src_folder)
            for filename in os.listdir():
                if f"_{part}" in filename:
                    tar.add(os.path.basename(filename))
                    count_files += 1

            os.chdir(wd)

        if count_files == 0:
            log.warning(f"No files found for part {part} in {src_folder}. Skipping upload.")
            return

        endpoint = jwt.decode(app_token, options={"verify_signature": False})['endpoint']
        msg_headers = {'Authorization' : f'Bearer {app_token}'}
        url = f"{endpoint}/file/{app_info['edge_id']}/upload"

        files = {'extract': open(tar_filename, 'rb')}
        values = {
            'filename': os.path.basename(tar_filename)
        }

        response = requests.post(url, files=files, data=values, headers=msg_headers, proxies=proxies)

        if response.status_code != 201:
            raise Exception(f"Failing upload extract files: {response.json()['error']['message']}")

        log.info(f"File {tar_filename} uploaded successfully.")

    except Exception as excp:
        log.error(f"An error occurred: {excp}")
# ---------------------------------------------------------------------------------------------------------------------

def check_files_in_date(date, part_id):
    src_folder = os.path.join(CONFIG["file-service"]["data_folder"], "video", date)
    if not os.path.isdir(src_folder):
        log.warning(f"Source folder {src_folder} does not exist.")
        return False

    files_found = any(part_id in f for f in os.listdir(src_folder))
    if not files_found:
        # log.warning(f"No files found for part {part_id} in {src_folder}.")
        return False

    return True
# ---------------------------------------------------------------------------------------------------------------------

if not "DB_URL" in os.environ:
    log.error("DB_URL environment variable not set.")
    exit(1)

db_url = os.environ["DB_URL"]
db_client = MongoClient(db_url).eyeflow

begin_date = datetime.datetime.combine(datetime.date.today() - datetime.timedelta(days=2), datetime.datetime.min.time())
end_date = datetime.datetime.combine(datetime.date.today(), datetime.datetime.max.time())

app_info, app_token = get_license()

uploaded_parts = []
if os.path.isfile("/opt/eyeflow/src/move_part_files.info"):
    with open("/opt/eyeflow/src/move_part_files.info", 'r') as fp:
        uploaded_parts = json.load(fp)

log.info(f"Collecting feed_back events from {begin_date} to {end_date}")

query = {
	"event_time": {
		"$gte": begin_date,
		"$lte": end_date
	},
    "result": "OK",
	"feedback_data.feedback_type": "falso_ok"
}

if db_client.events.count_documents(query) < 1:
    log.info("No events found")
    exit(0)

part_dates = {}
for event in db_client.events.find(query):
    # log.info(f"Processing event: {str(event['part_id'])[-5:]} - {event}")
    if event['feedback_data']['feedback_type'] != "falso_ok" or event["result"] != "OK":
        log.info(f"Feedback is not FalseOK for part {str(event['part_id'])[-5:]}, skipping.")
        continue

    if str(event["part_id"])[-5:] in uploaded_parts:
        log.info(f"Part {str(event['part_id'])[-5:]} already uploaded, skipping.")
        continue

    start_date = event["event_time"].strftime("%Y-%m-%d")
    start_date = start_date[0:4] + start_date[5:7] + start_date[8:10]
    if not check_files_in_date(start_date, str(event["part_id"])[-5:]):
        start_date = (event["event_time"] - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        start_date = start_date[0:4] + start_date[5:7] + start_date[8:10]
        if not check_files_in_date(start_date, str(event["part_id"])[-5:]):
            log.warning(f"No files found for part {str(event['part_id'])[-5:]} in both {start_date} and previous day. Skipping.")
            continue

    if start_date not in part_dates:
        part_dates[start_date] = []

    part_dates[start_date].append({
        "part_id": str(event["part_id"])
    })

if not part_dates:
    log.info("No valid parts found for upload.")
    exit(0)

part_list = []
for start_date in sorted(part_dates.keys()):
    log.info(f"Copying parts for date: {start_date}")

    for part in part_dates[start_date]:
        log.info(f"Part: {part['part_id'][-5:]}")
        part_list.append(f"{part['part_id'][-5:]}")
        upload_files_part(app_token, app_info, "video", start_date, part['part_id'][-5:])

last_date = sorted(part_dates.keys())[-1]

uploaded_parts.extend(part_list)
uploaded_parts = list(set(uploaded_parts))
with open("/opt/eyeflow/src/move_part_files.info", 'w') as fp:
    json.dump(uploaded_parts, fp, indent=2)
