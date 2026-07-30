.PHONY: install test lint api etl-run ml-train genai-embed genai-embed-teams frontend-dev

install:
	python3 -m venv backend/.venv
	backend/.venv/bin/pip install --no-cache-dir -r etl/requirements.txt -r backend/requirements-dev.txt -r backend/ml/requirements.txt -r backend/genai/requirements.txt

ml-train:
	cd backend/ml && ../.venv/bin/python train_rating_model.py
	cd backend/ml && ../.venv/bin/python train_outcome_model.py
	cd backend/ml && ../.venv/bin/python train_clustering.py

genai-embed:
	backend/.venv/bin/python backend/genai/generate_embeddings.py

genai-embed-teams:
	backend/.venv/bin/python backend/genai/generate_team_embeddings.py

test:
	cd backend && .venv/bin/python -m pytest tests/ -q
	backend/.venv/bin/python -m pytest etl/tests/ -q

lint:
	backend/.venv/bin/ruff check etl backend

etl-run:
	backend/.venv/bin/python etl/load.py

api:
	cd backend && .venv/bin/uvicorn app.main:app --reload

frontend-dev:
	cd frontend && npm run dev
