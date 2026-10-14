.PHONY: run grabar doctor test

run:
	uv run copiloto

grabar:
	uv run copiloto grabar

doctor:
	uv run copiloto doctor

test:
	uv run pytest -q
