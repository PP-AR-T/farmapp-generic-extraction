import json
from pathlib import Path
from typing import Any, Dict, Optional

from azure.core.exceptions import ResourceNotFoundError


class StateManager:
    def __init__(
        self,
        adls_service_client: Optional[Any] = None,
        state_container: str = "state",
        local_state_dir: Optional[str] = None,
    ):
        self.adls_service_client = adls_service_client
        self.state_container = state_container
        self.local_state_dir = local_state_dir

    def _state_file_name(self, job_name: str) -> str:
        return f"{job_name}.json"

    def load_state(self, job_name: str) -> Dict[str, Any]:
        file_name = self._state_file_name(job_name)

        if self.adls_service_client:
            fs = self.adls_service_client.get_file_system_client(self.state_container)
            file_client = fs.get_file_client(file_name)
            try:
                raw = file_client.download_file().readall().decode("utf-8")
                return json.loads(raw)
            except ResourceNotFoundError:
                return {}

        if not self.local_state_dir:
            return {}

        file_path = Path(self.local_state_dir) / file_name
        if not file_path.exists():
            return {}

        return json.loads(file_path.read_text(encoding="utf-8"))

    def save_state(self, job_name: str, state: Dict[str, Any]) -> None:
        payload = json.dumps(state, indent=2)
        file_name = self._state_file_name(job_name)

        if self.adls_service_client:
            fs = self.adls_service_client.get_file_system_client(self.state_container)
            file_client = fs.get_file_client(file_name)
            try:
                file_client.delete_file()
            except ResourceNotFoundError:
                pass
            file_client.create_file()
            data = payload.encode("utf-8")
            file_client.append_data(data=data, offset=0, length=len(data))
            file_client.flush_data(len(data))
            return

        if not self.local_state_dir:
            return

        local_dir = Path(self.local_state_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        file_path = local_dir / file_name
        file_path.write_text(payload, encoding="utf-8")
