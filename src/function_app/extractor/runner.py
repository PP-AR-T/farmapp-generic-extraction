import datetime as dt
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.filedatalake import DataLakeServiceClient

from .api_client import APIClient
from .auth import build_auth_headers
from .pagination import Paginator
from .sink import DataSink
from .state_manager import StateManager


def _extract_path(data: Any, path: Optional[str]) -> Any:
    if not path:
        return data

    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _to_utc_string() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _parse_datetime(value: Any) -> Optional[dt.datetime]:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return dt.datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


class ExtractionRunner:
    def __init__(
        self,
        adls_service_client: Optional[DataLakeServiceClient],
        secret_client: Optional[SecretClient],
        config_container: str = "configs",
        state_container: str = "state",
        local_output_dir: Optional[str] = None,
        local_state_dir: Optional[str] = None,
    ):
        self.adls_service_client = adls_service_client
        self.secret_client = secret_client
        self.config_container = config_container
        self.state_manager = StateManager(
            adls_service_client=adls_service_client,
            state_container=state_container,
            local_state_dir=local_state_dir,
        )
        self.sink = DataSink(adls_service_client=adls_service_client, local_output_dir=local_output_dir)

    @classmethod
    def from_azure_environment(cls) -> "ExtractionRunner":
        adls_account_name = os.getenv("ADLS_ACCOUNT_NAME")
        key_vault_uri = os.getenv("KEY_VAULT_URI")

        if not adls_account_name:
            raise ValueError("ADLS_ACCOUNT_NAME environment variable is required")
        if not key_vault_uri:
            raise ValueError("KEY_VAULT_URI environment variable is required")

        credential = DefaultAzureCredential()
        adls_service_client = DataLakeServiceClient(
            account_url=f"https://{adls_account_name}.dfs.core.windows.net",
            credential=credential,
        )
        secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)

        return cls(
            adls_service_client=adls_service_client,
            secret_client=secret_client,
            config_container=os.getenv("CONFIG_CONTAINER", "configs"),
            state_container=os.getenv("STATE_CONTAINER", "state"),
        )

    @classmethod
    def for_local(cls, local_output_dir: str = "./local_output") -> "ExtractionRunner":
        output_dir = Path(local_output_dir)
        state_dir = output_dir / "state"
        return cls(
            adls_service_client=None,
            secret_client=None,
            config_container="",
            state_container="state",
            local_output_dir=str(output_dir),
            local_state_dir=str(state_dir),
        )

    def _read_config_from_adls(self, job_name: str) -> Dict[str, Any]:
        config_path = f"jobs/{job_name}.json"
        fs = self.adls_service_client.get_file_system_client(self.config_container)
        file_client = fs.get_file_client(config_path)
        try:
            raw = file_client.download_file().readall().decode("utf-8")
            return json.loads(raw)
        except ResourceNotFoundError as exc:
            raise FileNotFoundError(f"Job config not found at {self.config_container}/{config_path}") from exc

    def _resolve_secret(self, secret_name: str) -> str:
        if self.secret_client:
            return self.secret_client.get_secret(secret_name).value

        env_name = secret_name.upper().replace("-", "_")
        value = os.getenv(env_name)
        if not value:
            raise ValueError(
                f"Missing secret for local mode. Set environment variable '{env_name}' for secret '{secret_name}'."
            )
        return value

    def _extract_records(self, payload: Any, data_path: Optional[str]) -> List[Dict[str, Any]]:
        data = _extract_path(payload, data_path)
        if data is None:
            return []

        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]

        if isinstance(data, dict):
            for key in ["items", "data", "results", "value"]:
                candidate = data.get(key)
                if isinstance(candidate, list):
                    return [row for row in candidate if isinstance(row, dict)]
            return [data]

        return []

    def _apply_incremental_filter(
        self,
        records: List[Dict[str, Any]],
        watermark_field: str,
        last_watermark: str,
    ) -> List[Dict[str, Any]]:
        last_value = _parse_datetime(last_watermark) or last_watermark
        filtered: List[Dict[str, Any]] = []

        for row in records:
            current_raw = row.get(watermark_field)
            if current_raw is None:
                continue

            current_value = _parse_datetime(current_raw) or str(current_raw)
            if current_value > last_value:
                filtered.append(row)

        return filtered

    def _update_max_watermark(
        self,
        records: List[Dict[str, Any]],
        watermark_field: str,
        current_max: Optional[str],
    ) -> Optional[str]:
        max_value = current_max
        max_comp = _parse_datetime(current_max) if current_max else None

        for row in records:
            raw = row.get(watermark_field)
            if raw is None:
                continue

            parsed = _parse_datetime(raw)
            if parsed is None:
                continue

            if max_comp is None or parsed > max_comp:
                max_comp = parsed
                max_value = raw if isinstance(raw, str) else parsed.isoformat()

        return max_value

    def _execute_job(self, config: Dict[str, Any]) -> Dict[str, Any]:
        job_name = config.get("job_name")
        if not job_name:
            raise ValueError("job_name is required in job config")

        source_cfg = config.get("source", {})
        auth_cfg = config.get("auth", {})
        pagination_cfg = config.get("pagination", {"type": "none"})
        sink_cfg = config.get("sink", {})
        incremental_cfg = config.get("incremental", {})

        if not source_cfg.get("base_url"):
            raise ValueError("source.base_url is required")
        if not source_cfg.get("endpoint"):
            raise ValueError("source.endpoint is required")

        incremental_enabled = bool(incremental_cfg.get("enabled", False))
        watermark_field = incremental_cfg.get("watermark_field")
        incremental_query_param = incremental_cfg.get("query_param")

        state = self.state_manager.load_state(job_name) if incremental_enabled else {}
        last_watermark = state.get("watermark") if incremental_enabled else None

        auth_headers = build_auth_headers(auth_cfg, self._resolve_secret)
        static_headers = source_cfg.get("headers", {})
        headers = {**static_headers, **auth_headers}

        client = APIClient(
            base_url=source_cfg["base_url"],
            timeout_seconds=int(source_cfg.get("timeout_seconds", 60)),
            max_retries=int(source_cfg.get("max_retries", 4)),
        )
        paginator = Paginator(pagination_cfg)
        pagination_state = paginator.initial_state()

        records: List[Dict[str, Any]] = []
        max_watermark = last_watermark
        total_pages = 0
        max_loops = int(pagination_cfg.get("max_loops", 10000))

        while True:
            total_pages += 1
            if total_pages > max_loops:
                raise RuntimeError(f"Pagination loop exceeded max_loops={max_loops} for job={job_name}")

            params = dict(source_cfg.get("query_params", {}))
            params.update(paginator.build_params(pagination_state))

            if incremental_enabled and incremental_query_param and last_watermark:
                params[incremental_query_param] = last_watermark

            endpoint_override = paginator.next_endpoint_override(pagination_state)
            payload = client.request(
                method=source_cfg.get("method", "GET"),
                endpoint=source_cfg["endpoint"],
                headers=headers,
                params=params,
                json_body=source_cfg.get("body"),
                endpoint_override=endpoint_override,
            )

            page_records = self._extract_records(payload, source_cfg.get("data_path"))
            raw_page_count = len(page_records)
            logging.info(
                "job=%s page=%s page_records=%s",
                job_name,
                total_pages,
                raw_page_count,
            )

            if incremental_enabled and last_watermark and watermark_field and not incremental_query_param:
                page_records = self._apply_incremental_filter(page_records, watermark_field, last_watermark)

            if incremental_enabled and watermark_field:
                max_watermark = self._update_max_watermark(page_records, watermark_field, max_watermark)

            records.extend(page_records)

            if not paginator.has_more(pagination_state, payload, raw_page_count):
                break
            pagination_state = paginator.advance(pagination_state, payload, raw_page_count)

        output_path = self.sink.write_records(records, sink_cfg, watermark_field=watermark_field)

        if incremental_enabled and watermark_field and max_watermark:
            self.state_manager.save_state(
                job_name,
                {
                    "job_name": job_name,
                    "watermark": max_watermark,
                    "updated_at": _to_utc_string(),
                },
            )

        return {
            "job_name": job_name,
            "records_extracted": len(records),
            "output_path": output_path,
            "pages_processed": total_pages,
            "start_time": _to_utc_string(),
        }

    def run_from_adls(self, job_name: str) -> Dict[str, Any]:
        if not self.adls_service_client:
            raise ValueError("ADLS client is not configured. Use run_from_file for local runs.")
        config = self._read_config_from_adls(job_name)
        return self._execute_job(config)

    def run_from_file(self, config_path: str) -> Dict[str, Any]:
        config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        return self._execute_job(config)
