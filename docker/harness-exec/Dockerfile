FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash coreutils ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 --shell /bin/bash harness
USER harness
WORKDIR /workspace/workflow

# Long-running workflow execution container; agent_service uses `docker exec`.
CMD ["sleep", "infinity"]
