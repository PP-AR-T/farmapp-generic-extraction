from typing import Any, Dict, Optional


def _extract_path(data: Any, path: Optional[str]) -> Any:
    if not path:
        return None

    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


class Paginator:
    def __init__(self, pagination_cfg: Dict[str, Any]):
        self.cfg = pagination_cfg or {}
        self.pagination_type = str(self.cfg.get("type", "none")).lower()

    def initial_state(self) -> Dict[str, Any]:
        if self.pagination_type == "page":
            return {"page": int(self.cfg.get("start_page", 1))}
        if self.pagination_type == "offset":
            return {"offset": int(self.cfg.get("start_offset", 0))}
        if self.pagination_type == "cursor":
            return {"cursor": self.cfg.get("start_cursor")}
        if self.pagination_type == "next_link":
            return {"next_url": None}
        return {}

    def build_params(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if self.pagination_type == "page":
            page_param = self.cfg.get("page_param", "page")
            page_size_param = self.cfg.get("page_size_param", "per_page")
            page_size = int(self.cfg.get("page_size", 100))
            return {page_param: state["page"], page_size_param: page_size}

        if self.pagination_type == "offset":
            offset_param = self.cfg.get("offset_param", "offset")
            limit_param = self.cfg.get("limit_param", "limit")
            limit = int(self.cfg.get("limit", 100))
            return {offset_param: state["offset"], limit_param: limit}

        if self.pagination_type == "cursor":
            cursor_param = self.cfg.get("cursor_param", "cursor")
            if state.get("cursor"):
                return {cursor_param: state["cursor"]}
            return {}

        return {}

    def next_endpoint_override(self, state: Dict[str, Any]) -> Optional[str]:
        if self.pagination_type == "next_link":
            return state.get("next_url")
        return None

    def has_more(self, state: Dict[str, Any], response_json: Any, records_count: int) -> bool:
        if self.pagination_type == "none":
            return False

        if self.pagination_type == "page":
            page_size = int(self.cfg.get("page_size", 100))
            max_pages = int(self.cfg.get("max_pages", 0))
            if max_pages and state["page"] >= max_pages:
                return False
            return records_count >= page_size

        if self.pagination_type == "offset":
            limit = int(self.cfg.get("limit", 100))
            max_pages = int(self.cfg.get("max_pages", 0))
            if max_pages:
                current_page = int(state.get("offset", 0) / max(limit, 1)) + 1
                if current_page >= max_pages:
                    return False
            return records_count >= limit

        if self.pagination_type == "cursor":
            next_cursor_field = self.cfg.get("next_cursor_field", "next_cursor")
            return bool(_extract_path(response_json, next_cursor_field))

        if self.pagination_type == "next_link":
            next_link_field = self.cfg.get("next_link_field", "next")
            return bool(_extract_path(response_json, next_link_field))

        return False

    def advance(self, state: Dict[str, Any], response_json: Any, records_count: int) -> Dict[str, Any]:
        next_state = dict(state)

        if self.pagination_type == "page":
            next_state["page"] += 1
            return next_state

        if self.pagination_type == "offset":
            next_state["offset"] += records_count
            return next_state

        if self.pagination_type == "cursor":
            next_cursor_field = self.cfg.get("next_cursor_field", "next_cursor")
            next_state["cursor"] = _extract_path(response_json, next_cursor_field)
            return next_state

        if self.pagination_type == "next_link":
            next_link_field = self.cfg.get("next_link_field", "next")
            next_state["next_url"] = _extract_path(response_json, next_link_field)
            return next_state

        return next_state
