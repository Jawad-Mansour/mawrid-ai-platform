"""
Feature:  Customer Management
Layer:    Core / Service
Module:   app.core.customers.services
Purpose:  Business logic for customer match waterfall (email→phone→name≥0.85
          match, 0.3–0.85 HITL, <0.3 auto-create), segment assignment, and
          payment history score updates used by dunning tone classifier.
Depends:  app.core.customers.models, app.core.hitl.services,
          app.infra.db.repos.customer_repo
HITL:     customer_match_review
"""
