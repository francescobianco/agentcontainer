PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
VENV ?= .venv
ACTIVATE = . $(VENV)/bin/activate

.PHONY: help venv install test pdf server-root server-a server-b docker-up docker-down docker-logs demo-send

help:
	@printf '%s\n' \
	'Targets:' \
	'  venv        Create local virtualenv' \
	'  install     Install package with dev dependencies into the venv' \
	'  test        Run pytest suite' \
	'  pdf         Regenerate WHITEPAPER.pdf' \
	'  server-root Run the root container service locally' \
	'  server-a    Run department-a locally' \
	'  server-b    Run department-b locally' \
	'  docker-up   Start the federated Docker lab' \
	'  docker-down Stop the federated Docker lab' \
	'  docker-logs Tail docker compose logs' \
	'  demo-send   Send the travelling scout to the local root node'

venv:
	$(PYTHON) -m venv $(VENV)

install: venv
	$(ACTIVATE) && $(PIP) install -e .[dev]

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
	PYTHONPATH=src $(PYTHON) -m agentcontainer.cli send agents/travelling_scout.py 127.0.0.1:7000 --secret root-admin-secret --activate '{"query":"scacchi","tour":true}'
