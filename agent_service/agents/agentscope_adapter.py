from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


def initialize_agentscope() -> bool:
    """Initialize AgentScope when the package is available.

    The MVP keeps execution deterministic, but the service is structured so
    real AgentScope message passing can replace the configured runner without
    changing backend or frontend contracts.
    """

    try:
        import agentscope  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional install
        logger.info("AgentScope is not available, using deterministic local runner: %s", exc)
        return False

    try:
        agentscope.init()
    except TypeError:
        agentscope.init(project="harness_platform")
    except Exception as exc:  # pragma: no cover - depends on package version
        logger.warning("AgentScope initialization failed, continuing with local runner: %s", exc)
        return False

    logger.info("AgentScope initialized")
    return True
