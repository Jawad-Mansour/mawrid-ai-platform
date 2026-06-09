"""
Feature:  AI Chatbot (3-Tier Intent Classifier)
Layer:    ML / Intent
Module:   app.ml.intent.classifier
Purpose:  3-tier intent classification pipeline:
          Tier 1: TF-IDF + Logistic Regression (< 5ms, 8 classes)
          Tier 2: DistilBERT ONNX (< 50ms, if Tier 1 confidence < 0.85)
          Tier 3: GPT-4o zero-shot (if Tier 2 confidence < 0.85)
          8 intent classes: product_search, price_inquiry, stock_check,
          order_status, supplier_query, payment_question, general_faq, other.
          Admin chatbot also routes operational queries → direct DB bypass.
Depends:  scikit-learn, onnxruntime, app.infra.llm.openai_client
HITL:     None — classification is internal.
"""
