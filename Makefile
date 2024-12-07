
.PHONY: host client check

host:
	rm -f /tmp/aap
	poetry run python example/host.py

client:
	poetry run python example/client.py

check:
	poetry update
	poetry run ruff check
	poetry run ruff format --check
	poetry install
	poetry run pytest --cov
	poetry run coverage html