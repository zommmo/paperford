.PHONY: run test

run:
	./run_app.sh

test:
	.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests
