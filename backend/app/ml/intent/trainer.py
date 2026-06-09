"""
Feature:  AI Chatbot (3-Tier Intent Classifier)
Layer:    ML / Intent
Module:   app.ml.intent.trainer
Purpose:  Training script for Tier 1 (TF-IDF+LR) and Tier 2 (DistilBERT fine-tune
          → ONNX export) classifiers. Consumes intent dataset from
          tests/evals/eval_dataset/intent_test_set.json (1200+ examples, 8 classes,
          150 per class). Outputs serialized models to backend/ml_models/.
Depends:  scikit-learn, transformers, optimum, onnx
HITL:     None.
"""
