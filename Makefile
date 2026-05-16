.PHONY: run web test frontend-build

run:
	./run_web.sh

web:
	./run_web.sh

test:
	.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests

frontend-build:
	cd frontend && npm run build
