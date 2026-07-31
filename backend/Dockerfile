# Serving image for the FastAPI backend. Deliberately excludes backend/ml's training
# scripts and backend/tests -- this is a *runtime* image, not a copy of the dev venv;
# training happens locally/CI and only the resulting artifacts (backend/ml/artifacts/)
# ship in the image.
FROM python:3.13-slim

WORKDIR /app

# libgomp1 (OpenMP runtime) isn't in the slim base image but xgboost's compiled
# extension links against it at import time -- omitting this gives a working `pip
# install` and a working `docker build`, then an ImportError the first time /predict
# is actually called. A real "passed the build, failed at runtime" gotcha to know.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY genai ./genai
COPY ml/artifacts ./ml/artifacts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
