import base64
from typing import Callable, Dict


def build_auth_headers(auth_cfg: Dict, secret_resolver: Callable[[str], str]) -> Dict[str, str]:
    auth_type = str(auth_cfg.get("type", "none")).lower()
    if auth_type in {"none", ""}:
        return {}

    if auth_type == "api_key":
        secret_name = auth_cfg.get("keyvault_secret_name")
        if not secret_name:
            raise ValueError("auth.keyvault_secret_name is required for api_key auth")

        header_name = auth_cfg.get("header_name", "x-api-key")
        value_prefix = auth_cfg.get("value_prefix", "")
        secret_value = secret_resolver(secret_name)
        return {header_name: f"{value_prefix}{secret_value}"}

    if auth_type == "bearer_token":
        secret_name = auth_cfg.get("keyvault_secret_name")
        if not secret_name:
            raise ValueError("auth.keyvault_secret_name is required for bearer_token auth")

        header_name = auth_cfg.get("header_name", "Authorization")
        token = secret_resolver(secret_name)
        if token.lower().startswith("bearer "):
            return {header_name: token}
        return {header_name: f"Bearer {token}"}

    if auth_type == "basic":
        username_secret = auth_cfg.get("username_secret_name")
        password_secret = auth_cfg.get("password_secret_name")
        if not username_secret or not password_secret:
            raise ValueError("basic auth requires username_secret_name and password_secret_name")

        user = secret_resolver(username_secret)
        password = secret_resolver(password_secret)
        token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("utf-8")
        return {"Authorization": f"Basic {token}"}

    raise ValueError(f"Unsupported auth type: {auth_type}")
