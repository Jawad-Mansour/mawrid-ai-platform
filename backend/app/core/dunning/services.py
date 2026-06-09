"""
Feature:  Dunning Engine (4 Tracks)
Layer:    Core / Service
Module:   app.core.dunning.services
Purpose:  Business logic for all 4 dunning tracks. Trigger logic always
          uses due_date as the anchor. Payment auto-stop: on payment webhook,
          atomically marks invoice paid AND cancels all pending dunning actions
          in single transaction. Track 2 (disputes) mode-gated: Retail Only
          tenants get 403. Tone classifier integration (3-class ML, SMOTE,
          random_state=42).
Depends:  app.core.dunning.models, app.core.hitl.services,
          app.ml.tone.classifier, app.infra.db.repos.dunning_repo
HITL:     dunning_payables_advance, dunning_disputes_on_demand,
          dunning_receivables_day7/14/21, dunning_b2c_day3/7/14
"""
