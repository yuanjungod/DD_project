from __future__ import annotations

import time
import subprocess
from unittest.mock import patch

from agent_service.execution.container_manager import ContainerManager


def _docker_ok() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, "", "")


def _running_inspect(*, started_at: str, idle_ttl: str = "120") -> dict:
    return {
        "State": {"Running": True, "StartedAt": started_at},
        "Config": {"Labels": {"harness.idle_ttl_seconds": idle_ttl, "harness.role": "workflow-exec"}},
        "Mounts": [],
    }


class TestContainerManagerIdlePrune:
    def test_prune_stops_container_past_ttl(self) -> None:
        mgr = ContainerManager()
        name = "harness-exec-user1-tpl1"
        started = "2020-01-01T00:00:00.000000000Z"
        mgr._last_activity[name] = time.time() - 200
        mgr._idle_ttl_by_container[name] = 120

        with (
            patch(
                "agent_service.execution.container_manager._list_harness_exec_container_names",
                return_value=[name],
            ),
            patch(
                "agent_service.execution.container_manager._container_inspect",
                return_value=_running_inspect(started_at=started, idle_ttl="120"),
            ),
            patch(
                "agent_service.execution.container_manager._run_docker",
                return_value=_docker_ok(),
            ) as run_docker,
        ):
            stopped = mgr.prune_idle_containers()

        assert stopped == [name]
        run_docker.assert_called_once_with(["stop", "-t", "10", name])
        assert name not in mgr._last_activity

    def test_prune_keeps_active_container(self) -> None:
        mgr = ContainerManager()
        name = "harness-exec-user2-tpl2"
        mgr.touch_activity(name)
        mgr._idle_ttl_by_container[name] = 1200

        with (
            patch(
                "agent_service.execution.container_manager._list_harness_exec_container_names",
                return_value=[name],
            ),
            patch(
                "agent_service.execution.container_manager._container_inspect",
                return_value=_running_inspect(started_at="2020-01-01T00:00:00.000000000Z"),
            ),
            patch("agent_service.execution.container_manager._run_docker") as run_docker,
        ):
            stopped = mgr.prune_idle_containers()

        assert stopped == []
        run_docker.assert_not_called()
