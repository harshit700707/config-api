import importlib.util
import os

if importlib.util.find_spec("yaml") is not None:
    import yaml
else:
    yaml = None

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000"
}

def to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("true", "1", "yes", "on")

def load_config():
    config = DEFAULTS.copy()

    # config.development.yaml
    try:
        with open("config.development.yaml") as f:
            yaml_config = yaml.safe_load(f) or {}
        config.update(yaml_config)
    except FileNotFoundError:
        pass

    # .env
    if os.getenv("NUM_WORKERS") is not None:
        config["workers"] = os.getenv("NUM_WORKERS")

    if os.getenv("APP_DEBUG") is not None:
        config["debug"] = os.getenv("APP_DEBUG")

    if os.getenv("APP_API_KEY") is not None:
        config["api_key"] = os.getenv("APP_API_KEY")

    # OS environment variables
    env_map = {
        "APP_PORT": "port",
        "APP_WORKERS": "workers",
        "APP_DEBUG": "debug",
        "APP_API_KEY": "api_key"
    }

    for env_name, key in env_map.items():
        if os.getenv(env_name) is not None:
            config[key] = os.getenv(env_name)

    config["port"] = int(config["port"])
    config["workers"] = int(config["workers"])
    config["debug"] = to_bool(config["debug"])

    return config


@app.get("/effective-config")
async def effective_config(request: Request):
    config = load_config()

    # CLI overrides: ?set-key=value
    for key, value in request.query_params.multi_items():
        if key.startswith("set-"):
            config_key = key[4:]
            if config_key in config:
                config[config_key] = value

    # type coercion
    config["port"] = int(config["port"])
    config["workers"] = int(config["workers"])
    config["debug"] = to_bool(config["debug"])

    # mask secret
    config["api_key"] = "****"

    return config