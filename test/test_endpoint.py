import os
import json
import jwt
import datetime
import socket
import base64

from pymongo.mongo_client import MongoClient
from bson.objectid import ObjectId
from azure.storage.blob import BlobServiceClient
# ---------------------------------------------------------------------------------------------------------------------


def create_endpoint(environment_name, flow_name):
    # if plat == "dev":
    #     parms_file = os.path.join(os.environ['HOME'], ".eyeflow", "env_credentials_dev.json")
    # elif plat == "beta":
    #     parms_file = os.path.join(os.environ['HOME'], ".eyeflow", "env_credentials_beta.json")
    # elif plat == "prod":
    parms_file = os.path.join(os.environ['HOME'], ".eyeflow", "env_credentials_prod.json")

    with open(parms_file) as fp:
        parms = json.load(fp)

    db_auth_client = MongoClient(parms["atlas"]["db_url"])
    db_auth = db_auth_client["eyeflow-auth"]

    env_credentials = db_auth.environment.find_one({"name": environment_name})
    if not env_credentials:
        raise Exception(f"Environment not found {environment_name}")

    db_config = env_credentials["db_resource"]
    db_url = db_config["db_url"].replace("-pri", "")
    client = MongoClient(db_url)
    db_client = client[db_config["db_name"]]

    flow_doc = db_client.flow.find_one({"name": flow_name})
    if not flow_doc:
        raise Exception(f"Flow not found {flow_name}")


    app_data = db_auth.app.find_one({"name": "endpoint_demonstration_2h"})
    if app_data is None:
        raise Exception(f"App not found endpoint_demonstration_2h")

    app_id = str(app_data["_id"])
    app_name = str(app_data["name"])
    endpoint = str(app_data["endpoint"])


    endpoint_id = ObjectId()
    token_id = ObjectId()

    token_payload = {
        "token_id": str(token_id),
        "endpoint_id": str(endpoint_id),
        "app_id": app_id,
        "app_name": app_name,
        "environment_id": str(env_credentials["_id"]),
        "environment_name": environment_name,

        "endpoint": endpoint,
        "endpoint_parms": {
            "flow_id": str(flow_doc["_id"]),
            "flow_name": flow_name
        },
        "bill_parms": parms["bill_parms"],
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
    }

    token_key = db_auth.token_key.find_one({"_id": ObjectId(app_data["token_key"]["$oid"])})
    if token_key is None:
        raise Exception(f"Token key not found {app_data['token_key']}")

    private_key = token_key["private_key"]
    endpoint_token = jwt.encode(token_payload, base64.b64decode(private_key), algorithm='RS256').decode('utf-8')


    edge_token = {
        "_id": token_id,
        "active": True,
        "token": endpoint_token,
        "payload": token_payload,
        "token_key": ObjectId(app_data["token_key"]["$oid"]),
        "acl_type": app_data["options"]["acl_type"],
        "info": {
            "creation_date": datetime.datetime.now(datetime.timezone.utc)
        }
    }

    db_auth.edge_tokens.insert_one(edge_token)

    endpoint_doc = {
        "_id": endpoint_id,
        "env_id": str(env_credentials["_id"]),
        "name": flow_name,
        "info": {
            "owner": "5fb5a97cb687b9f2d532288f",
            "license": {
                "token": token_id,
                "app_id": str(app_data["_id"]),
                "app_name": app_data["name"]
            },
            "creation_date": datetime.datetime.now(datetime.timezone.utc)
        },
        "flow_id": flow_doc["_id"],
        "flow_modified_date": flow_doc["modified_date"],
        "flow_name": flow_doc["name"],
        "package_id": flow_doc["package"],
        "active": True
    }

    db_client.endpoint.insert_one(endpoint_doc)

    public_key = base64.b64decode(token_key["public_key"]).decode('utf-8')

    return {
        "endpoint_id": endpoint_id,
        "endpoint_token": endpoint_token,
        "pub_key": public_key
    }
# ---------------------------------------------------------------------------------------------------------------------

hostname = socket.gethostname()

endpoint_data = create_endpoint("Eyeflow", "teste_endpoint")

print(endpoint_data)
