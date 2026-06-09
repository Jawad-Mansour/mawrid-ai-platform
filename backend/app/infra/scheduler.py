"""
Feature:  Dunning Engine (cross-cutting)
Layer:    Infra / Scheduler
Module:   app.infra.scheduler
Purpose:  APScheduler instance. Registers all daily dunning check jobs:
          Track 1 (payables advance, due_date - 3), Track 3 (receivables
          day 7/14/21 from due_date), Track 4 (B2C day 3/7/14 from
          invoice_date). Started in main.py lifespan startup. Triggers
          dunning service per schedule — never sends without HITL approval.
Depends:  apscheduler, app.core.dunning.services
HITL:     All downstream actions are HITL-gated in dunning services.
"""
