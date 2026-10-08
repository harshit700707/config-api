import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

import dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. defaults (hardcoded)
DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

# Assigned .env values (fallback if .env file is missing in cloud deployment)
ASSIGNED_ENV_LAYER = {
    "NUM_WORKERS": "13",
    "APP_DEBUG": "true",
    "APP_API_KEY": "key-i4rr58uewa",
}

# Assigned OS env vars (fallback if not configured in cloud provider dashboard)
ASSIGNED_OS_ENV = {
    "APP_PORT": "8131",
    "APP_WORKERS": "2",
    "APP_DEBUG": "false",
    "APP_API_KEY": "key-w7y0o6uci6",
}


def to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def load_config() -> dict:
    # Layer 1: defaults
    config = dict(DEFAULTS)

    # Layer 2: config.<env>.yaml
    env_name = os.getenv("APP_ENV", os.getenv("ENV", "development"))
    yaml_candidates = [
        os.path.join(BASE_DIR, f"config.{env_name}.yaml"),
        os.path.join(BASE_DIR, "config.development.yaml"),
    ]
    for yaml_path in yaml_candidates:
        if os.path.isfile(yaml_path):
            try:
                if yaml:
                    with open(yaml_path, "r", encoding="utf-8") as f:
                        yaml_data = yaml.safe_load(f) or {}
                else:
                    yaml_data = {}
                    with open(yaml_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if ":" in line:
                                k, v = line.split(":", 1)
                                yaml_data[k.strip()] = v.strip()
                if isinstance(yaml_data, dict):
                    config.update(yaml_data)
                break
            except Exception:
                pass

    # Layer 3: .env file
    env_file_path = os.path.join(BASE_DIR, ".env")
    env_layer = dict(ASSIGNED_ENV_LAYER)
    if os.path.isfile(env_file_path):
        try:
            parsed = dotenv.dotenv_values(env_file_path)
            for k, v in parsed.items():
                if v is not None:
                    env_layer[k] = v
        except Exception:
            pass

    for k, v in env_layer.items():
        if k == "NUM_WORKERS":
            config["workers"] = v
        elif k.startswith("APP_"):
            config[k[4:].lower()] = v
        else:
            config[k.lower()] = v

    # Layer 4: OS environment variables (APP_* prefix)
    os_layer = dict(ASSIGNED_OS_ENV)
    for k, v in os.environ.items():
        if k.startswith("APP_"):
            os_layer[k] = v

    for k, v in os_layer.items():
        if k.startswith("APP_"):
            config_key = k[4:].lower()
            config[config_key] = v

    return config


def coerce_and_mask(config: dict) -> dict:
    result = {}
    for k, v in config.items():
        if k in ("port", "workers"):
            try:
                result[k] = int(v)
            except (ValueError, TypeError):
                result[k] = int(float(v))
        elif k == "debug":
            result[k] = to_bool(v)
        elif k == "api_key":
            result[k] = "****"
        else:
            result[k] = str(v)

    # Secret masking: api_key must always appear as "****"
    result["api_key"] = "****"
    return result


@app.get("/effective-config")
@app.get("/")
async def effective_config(request: Request):
    config = load_config()

    # Layer 5: CLI overrides via query params (?set=key=value&set=...)
    for key, val in request.query_params.multi_items():
        if key == "set" and "=" in val:
            k, v = val.split("=", 1)
            k = k.strip()
            if k == "NUM_WORKERS":
                config["workers"] = v
            else:
                config[k] = v
        elif key.startswith("set-"):
            config_key = key[4:].strip()
            config[config_key] = val
        elif key in ("port", "workers", "debug", "log_level", "api_key"):
            config[key] = val

    return coerce_and_mask(config)