FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md DESIGN.md WHITEPAPER.md /app/
COPY src /app/src
COPY agents /app/agents
COPY examples /app/examples
COPY fixtures /app/fixtures
COPY scripts /app/scripts

RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "agentcontainer.server", "--config", "/app/examples/root.json"]
