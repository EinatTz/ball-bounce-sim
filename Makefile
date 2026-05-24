.PHONY: all run test lint clean

PYTHON  := python3
VENV    := venv
PIP     := $(VENV)/bin/pip
PYTEST  := $(VENV)/bin/pytest
RUFF    := $(VENV)/bin/ruff
RUN     := $(VENV)/bin/python

# ── Default target: set up and run the simulation ─────────────────────────────
all: $(VENV) run

# ── Create venv and install dependencies ──────────────────────────────────────
$(VENV): requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip --quiet
	$(PIP) install -r requirements.txt --quiet
	@touch $(VENV)

# ── Run the simulation ────────────────────────────────────────────────────────
run: $(VENV)
	$(RUN) main.py

# ── Run all tests ─────────────────────────────────────────────────────────────
test: $(VENV)
	$(PYTEST) tests/ -v

# ── Lint ──────────────────────────────────────────────────────────────────────
lint: $(VENV)
	$(RUFF) check .

# ── Remove venv and output ────────────────────────────────────────────────────
clean:
	rm -rf $(VENV) output/ __pycache__ .pytest_cache
