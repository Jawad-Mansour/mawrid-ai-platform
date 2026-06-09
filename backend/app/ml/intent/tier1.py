"""
Feature:  AI Agents — Intent Classification (Tier 1)
Layer:    ML / Intent
Module:   app.ml.intent.tier1
Purpose:  TF-IDF + Logistic Regression classifier. Handles ~80% of traffic
          at sub-millisecond latency. 8 classes: product_search, order_status,
          stock_check, shipment_status, invoice_query, dunning_action,
          complex_task, out_of_scope. If confidence < threshold, escalates
          to Tier 2 (DistilBERT ONNX). Loaded from MLflow registry at startup.
Depends:  scikit-learn, mlflow, numpy
HITL:     None — classification is internal.
"""
