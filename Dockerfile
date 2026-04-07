FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md DESIGN.md WHITEPAPER.md /app/
COPY src /app/src
COPY agents /app/agents
COPY fixtures /app/fixtures
COPY scripts /app/scripts

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -e .

CMD ["agentcontainer", "server", "0.0.0.0:7000"]
