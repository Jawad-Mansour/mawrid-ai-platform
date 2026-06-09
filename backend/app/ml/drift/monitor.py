"""
Feature:  Model Health & Drift Detection (cross-cutting)
Layer:    ML / Drift
Module:   app.ml.drift.monitor
Purpose:  Population Stability Index (PSI) monitoring for intent classifier,
          tone classifier, and supplier scorer. Reads thresholds from
          backend/ml_config/drift_thresholds.yaml. Alerts via n8n WF-15 when
          PSI > 0.2 (severe) or > 0.1 (warning). Runs in nightly CI gate.
Depends:  numpy, scipy, app.infra.db.repos
HITL:     None — drift is automated monitoring.
"""
