lint:
	uv run mypy .

test: lint
	uv run python3 -m unittest
