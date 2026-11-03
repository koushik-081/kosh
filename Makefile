# Kosh shortcuts. Run `make` to see them.
KOSH := uv run python -m app.cli
PAPER := https://proceedings.neurips.cc/paper_files/paper/2017/file/3f5ee243547dee91fbd053c1c4a845aa-Paper.pdf

.PHONY: help setup demo-data run api ui phoenix eval report

help:  ## show this list
	@grep -E "^[a-z-]+:.*## " Makefile | sed "s/:.*## /\t/" | expand -t 12

setup:  ## one-time setup: packages, database, models (safe to re-run)
	./scripts/setup.sh

demo-data:  ## add the demo sources (~10 min on CPU; already-saved chunks are skipped)
	$(KOSH) ingest https://fastapi.tiangolo.com/tutorial/path-params/ -c fastapi
	$(KOSH) ingest https://fastapi.tiangolo.com/tutorial/dependencies/ -c fastapi
	$(KOSH) ingest "https://www.youtube.com/watch?v=tLKKmouUams" -c fastapi
	$(KOSH) ingest https://github.com/fastapi/fastapi --path fastapi -c fastapi
	mkdir -p data
	if curl -sfL --max-time 120 -o data/attention.pdf $(PAPER); then \
		$(KOSH) ingest data/attention.pdf -c papers; \
	else echo "Could not download the Attention paper, skipping it (add any PDF on the Sources page)"; fi

run:  ## start the API and the dashboard together (Ctrl+C stops both)
	@echo "Dashboard: http://localhost:8501   API: http://localhost:8010/docs"
	@trap "kill 0" INT TERM; \
	uv run uvicorn app.api.main:app --port 8010 & \
	uv run streamlit run ui/app.py --server.address localhost --server.headless true & \
	wait

api:  ## only the API, reloading on code changes
	uv run uvicorn app.api.main:app --port 8010 --reload

ui:  ## only the dashboard
	uv run streamlit run ui/app.py --server.address localhost

phoenix:  ## tracing UI at http://localhost:6006
	uvx arize-phoenix serve

eval:  ## re-run the evaluation for both modes (slow: ~2-3 h on CPU), then the report
	uv run python -m eval.run --mode naive
	uv run python -m eval.run --mode agent
	uv run python -m eval.report

report:  ## rebuild eval/report.md from the saved results
	uv run python -m eval.report
