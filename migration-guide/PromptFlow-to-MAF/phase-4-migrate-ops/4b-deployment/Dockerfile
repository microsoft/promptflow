# Build context must be the PromptFlow-to-MAF/ root directory.
# The deploy.sh script sets this automatically via 'az acr build . --file ...'.
# Do not run 'docker build' from this subdirectory directly.
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY workflow_loader.py ./workflow_loader.py
COPY phase-2-rebuild ./phase-2-rebuild
COPY phase-4-migrate-ops/4b-deployment ./phase-4-migrate-ops/4b-deployment
EXPOSE 8000
WORKDIR /app/phase-4-migrate-ops/4b-deployment
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
