.PHONY: all venv run test update clean

all: venv

venv: .venv/bin/python
.venv/bin/python:
	python3 -m venv .venv
	.venv/bin/pip install -e .

run: venv
	.venv/bin/python pysol.py

test: venv
	.venv/bin/python -m tests.qa

# Pull the latest code + refresh dependencies. Safe to run repeatedly;
# editable install is idempotent.
update:
	git pull
	.venv/bin/pip install -e .

clean:
	rm -rf .venv *.egg-info tests/out/*.svg tests/out/*.png
