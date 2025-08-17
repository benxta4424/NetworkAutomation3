import json

from conda.common.serialize import yaml_safe_load
from jsonpatch import JsonPatch
from ruamel.yaml import YAML

def get_info():
    info = {}

    dev_name = input("Give me your device name please:")
    prt_number = input("Your port number:")
    ip_add = input("Ip address:")
    prt_speed = int(input("Your speed for the chosen port:"))

    info["device"] = dev_name
    info["port_number"] = prt_number
    info["ip_adress"] = ip_add
    info["port_speed"] = prt_speed

    return info

get_result = get_info()

#parsing with JSON
json_result = json.dumps(get_result, indent=5)
print(json_result)

#get Yaml
yaml_parse = YAML()

with open("yaml_result.yaml", "w") as file:
    yaml_parse.dump(get_result ,file)