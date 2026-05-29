from __future__ import annotations

import logging
import threading

from agent_service.execution.container_manager import get_container_manager

logger = logging.getLogger(__name__)

_SWEEP_INTERVAL_SECONDS = 60
_stop_event = threading.Event()
_thread: threading.Thread | None = None


def _sweeper_loop() -> None:
    while not _stop_event.wait(_SWEEP_INTERVAL_SECONDS):
        try:
            stopped = get_container_manager().prune_idle_containers()
            if stopped:
                logger.debug("Idle container sweep stopped: %s", stopped)
        except Exception:
            logger.exception("Idle workflow container sweep failed")


def start_idle_container_sweeper() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_sweeper_loop, name="harness-idle-container-sweeper", daemon=True)
    _thread.start()
    logger.info("Started workflow container idle sweeper (interval=%ss)", _SWEEP_INTERVAL_SECONDS)


def stop_idle_container_sweeper() -> None:
    _stop_event.set()
