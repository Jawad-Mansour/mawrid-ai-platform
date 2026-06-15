-- Creates additional databases needed by n8n, MLflow, and the integration tests.
-- Runs automatically on first postgres container start (docker-entrypoint-initdb.d).
CREATE DATABASE n8n;
CREATE DATABASE mlflow;
-- Integration tests (Gate 4/5) default DATABASE_URL points at mawrid_test so they
-- never touch the dev database. Mirrors the CI service-container DB name.
CREATE DATABASE mawrid_test;
