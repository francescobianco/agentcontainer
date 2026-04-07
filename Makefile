PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: help install install-venv venv test pdf server-root server-a server-b docker-up docker-down docker-logs demo-send demo-run

help:
	@printf '%s\n' \
	'Targets:' \
	'  install     Install the CLI in the current Python environment' \
	'  install-venv Create a local virtualenv and install the project there' \
	'  venv        Create local virtualenv only' \
	'  test        Run pytest suite' \
	'  pdf         Regenerate WHITEPAPER.pdf' \
	'  server-root Run the root container service locally' \
	'  server-a    Run department-a locally' \
	'  server-b    Run department-b locally' \
	'  docker-up   Start the federated Docker lab' \
	'  docker-down Stop the federated Docker lab' \
	'  docker-logs Tail docker compose logs' \
	'  demo-send   Send the travelling scout to the local root node' \
	'  demo-run    Run the travelling scout in an isolated temporary local container'

venv:
	$(PYTHON) -m venv $(VENV)

install:
	$(PIP) install -e .[dev]

install-venv: venv
	. $(VENV)/bin/activate && $(PIP) install -e .[dev]

test:
	PYTHONPATH=src pytest -q

pdf:
	$(PYTHON) scripts/generate_whitepaper_pdf.py

server-root:
	PYTHONPATH=src $(PYTHON) -m agentcontainer.cli server --config examples/root.json

server-a:
	PYTHONPATH=src $(PYTHON) -m agentcontainer.cli server --config examples/department_a.json

server-b:
	PYTHONPATH=src $(PYTHON) -m agentcontainer.cli server --config examples/department_b.json

docker-up:
	docker compose up --build

docker-down:
	docker compose down --remove-orphans

docker-logs:
	docker compose logs -f

demo-send:
	PYTHONPATH=src $(PYTHON) -m agentcontainer.cli send agents/demo/visitcontainer-and-go-back.py 127.0.0.1:7000

demo-run:
	PYTHONPATH=src $(PYTHON) -m agentcontainer.cli run agents/demo/visitcontainer-and-go-back.py
