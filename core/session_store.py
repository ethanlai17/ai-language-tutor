import json
from core.state_machine import SessionState
from db import queries


_cache: dict[int, SessionState] = {}


def get(user_id: int) -> SessionState:
    if user_id in _cache:
        return _cache[user_id]
    row = queries.load_session(user_id)
    if row:
        ctx = json.loads(row["context_json"] or "{}")
        ctx["state"] = row["state"]
        state = SessionState.from_dict(ctx)
    else:
        state = SessionState()
    _cache[user_id] = state
    return state


def save(user_id: int, state: SessionState) -> None:
    _cache[user_id] = state
    queries.save_session(user_id, state.state.value, state.to_dict())
