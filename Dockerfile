FROM python:3.12-slim

ARG NODE_MAJOR=20
ARG CODEX_CLI_VERSION=0.101.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git openssh-client gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g "@openai/codex@${CODEX_CLI_VERSION}" \
    && apt-get purge -y --auto-remove gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 agent

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY agent_fleet /app/agent_fleet
RUN pip install --no-cache-dir .

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /workspace /data \
    && chown -R agent:agent /workspace /data /app /home/agent

USER agent
ENV HOME=/home/agent \
    AGENT_FLEET_DATABASE=/data/agent_fleet.db \
    AGENT_FLEET_RUNTIME_DIR=/data/runtime \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["run"]
