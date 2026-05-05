"""Instance registry — CRUD for ~/.horavox/data.json."""

import json
import os
import uuid

from horavox.core import USER_DIR

REGISTRY_PATH = os.path.join(USER_DIR, "data.json")


def _load():
    if not os.path.exists(REGISTRY_PATH):
        return {"instances": []}
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    os.makedirs(USER_DIR, exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def list_instances():
    return _load()["instances"]


def add_instance(command):
    data = _load()
    instance_id = uuid.uuid4().hex[:6]
    from datetime import datetime, timezone

    entry = {
        "id": instance_id,
        "command": command,
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }
    data["instances"].append(entry)
    _save(data)
    return entry


def remove_instance(instance_id):
    data = _load()
    before = len(data["instances"])
    data["instances"] = [i for i in data["instances"] if i["id"] != instance_id]
    if len(data["instances"]) == before:
        return False
    _save(data)
    return True


def remove_all():
    data = _load()
    count = len(data["instances"])
    data["instances"] = []
    _save(data)
    return count


def get_instance(instance_id):
    for inst in list_instances():
        if inst["id"] == instance_id:
            return inst
    return None
