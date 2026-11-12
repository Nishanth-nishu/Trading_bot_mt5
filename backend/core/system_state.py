"""Persisted operating state and audit helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.config.settings import OperatingMode
from backend.database.models import AuditLog, SystemState


def audit(session: Session, category: str, event: str, detail: str | None = None) -> None:
    session.add(AuditLog(category=category, event=event, detail=detail))


def get_state(session: Session) -> SystemState:
    state = session.get(SystemState, 1)
    if state is None:
        state = SystemState(id=1, operating_mode=OperatingMode.RESEARCH.value)
        session.add(state)
        session.flush()
    return state


def reset_on_startup(session: Session) -> SystemState:
    """Never resume trading silently after a restart.

    Whatever mode was persisted, the process starts in research mode;
    autonomous demo execution needs a fresh explicit activation. The kill
    switch is left as it was: a restart must not clear it.
    """
    state = get_state(session)
    if state.operating_mode != OperatingMode.RESEARCH.value:
        audit(
            session,
            "system",
            "mode_reset_on_startup",
            f"{state.operating_mode} -> {OperatingMode.RESEARCH.value}",
        )
        state.operating_mode = OperatingMode.RESEARCH.value
    session.commit()
    return state
