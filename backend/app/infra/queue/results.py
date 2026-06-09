"""
Feature:  Catalog Enrichment Pipeline
Layer:    Infra / Queue
Module:   app.infra.queue.results
Purpose:  Poll ARQ job status from the Redis result store. Returns job state
          (queued / in_progress / complete / failed) for a given job_id.
          Used by the API layer to stream enrichment progress to the frontend.
Depends:  arq, redis
HITL:     None — queue infrastructure only.
"""
