import datetime as dt
import io
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pyarrow as pa
import pyarrow.parquet as pq
from azure.core.exceptions import ResourceExistsError


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


def _ensure_directory(fs_client: Any, directory_path: str) -> None:
    if not directory_path:
        return

    current = ""
    for part in directory_path.split("/"):
        current = f"{current}/{part}" if current else part
        dir_client = fs_client.get_directory_client(current)
        try:
            dir_client.create_directory()
        except ResourceExistsError:
            pass


class DataSink:
    def __init__(self, adls_service_client: Optional[Any] = None, local_output_dir: Optional[str] = None):
        self.adls_service_client = adls_service_client
        self.local_output_dir = local_output_dir

    def _partition_segments(
        self,
        record: Dict[str, Any],
        partition_by: List[str],
        sink_cfg: Dict[str, Any],
        watermark_field: Optional[str],
    ) -> Tuple[Tuple[str, str], ...]:
        segments: List[Tuple[str, str]] = []
        now = dt.datetime.utcnow()

        for field in partition_by:
            if field == "date":
                partition_source_field = sink_cfg.get("partition_source_field", watermark_field)
                source_value = record.get(partition_source_field) if partition_source_field else None
                parsed = _parse_datetime(source_value) or now
                segments.extend(
                    [
                        ("year", parsed.strftime("%Y")),
                        ("month", parsed.strftime("%m")),
                        ("day", parsed.strftime("%d")),
                    ]
                )
            else:
                raw = record.get(field, "unknown")
                segments.append((field, str(raw)))

        return tuple(segments)

    def write_records(
        self,
        records: List[Dict[str, Any]],
        sink_cfg: Dict[str, Any],
        watermark_field: Optional[str] = None,
    ) -> str:
        if not records:
            return ""

        sink_format = str(sink_cfg.get("format", "parquet")).lower()
        if sink_format != "parquet":
            raise ValueError(f"Unsupported sink format: {sink_format}")

        container = sink_cfg.get("container", "bronze")
        dataset = sink_cfg.get("dataset", "default")
        partition_by = sink_cfg.get("partition_by", [])

        grouped: Dict[Tuple[Tuple[str, str], ...], List[Dict[str, Any]]] = {}
        for record in records:
            key = self._partition_segments(record, partition_by, sink_cfg, watermark_field)
            grouped.setdefault(key, []).append(record)

        first_path = ""
        for partitions, grouped_records in grouped.items():
            partition_path = "/".join([f"{k}={v}" for k, v in partitions])
            relative_dir = f"{dataset}/{partition_path}" if partition_path else dataset
            file_name = f"part-{uuid.uuid4().hex}.parquet"
            file_path = f"{relative_dir}/{file_name}" if relative_dir else file_name

            table = pa.Table.from_pylist(grouped_records)
            buffer = io.BytesIO()
            pq.write_table(table, buffer)
            payload = buffer.getvalue()

            if self.adls_service_client:
                fs = self.adls_service_client.get_file_system_client(container)
                _ensure_directory(fs, relative_dir)
                file_client = fs.get_file_client(file_path)
                file_client.create_file()
                file_client.append_data(data=payload, offset=0, length=len(payload))
                file_client.flush_data(len(payload))
                output_path = f"{container}/{file_path}"
            else:
                if not self.local_output_dir:
                    raise ValueError("local_output_dir is required when ADLS client is not configured")
                local_dir = Path(self.local_output_dir) / container / relative_dir
                local_dir.mkdir(parents=True, exist_ok=True)
                local_file = local_dir / file_name
                local_file.write_bytes(payload)
                output_path = str(local_file)

            if not first_path:
                first_path = output_path

        return first_path
