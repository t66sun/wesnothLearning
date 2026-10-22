PYTHON ?= python3

.PHONY: test smoke doctor
test:
	$(PYTHON) -m unittest discover -s tests

smoke:
	$(PYTHON) tests/smoke_native.py

doctor:
	$(PYTHON) arena.py doctor
