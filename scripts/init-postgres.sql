-- Creates additional databases needed by n8n and MLflow.
-- Runs automatically on first postgres container start (docker-entrypoint-initdb.d).
CREATE DATABASE n8n;
CREATE DATABASE mlflow;
