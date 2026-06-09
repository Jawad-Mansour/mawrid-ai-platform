"""
Feature:  Supplier Intelligence
Layer:    Core / Service
Module:   app.core.suppliers.services
Purpose:  Business logic for supplier matching waterfall (exact→TF-IDF/embedding
          ≥0.9→0.3–0.9 HITL→<0.3 HITL "create new supplier?"), delivery event
          recording, score computation (Ridge regression, 6 features), customer
          matching waterfall (email→phone→name≥0.85→0.3–0.85 HITL→<0.3 auto-create),
          reorder threshold monitoring, and supplier discovery outreach.
Depends:  app.core.suppliers.models, app.core.hitl.services,
          app.ml.supplier_scorer, app.infra.db.repos.supplier_repo
HITL:     supplier_match_review, supplier_outreach, purchase_order_send (reorder)
"""
