"""
Feature:  AI Agents — Intent Classification (Tier 2)
Layer:    ML / Intent
Module:   app.ml.intent.tier2
Purpose:  DistilBERT fine-tuned on intent dataset, exported to ONNX Runtime
          for < 100ms inference. Handles cases where Tier 1 confidence is
          below threshold. Same 8 classes as Tier 1. If confidence < threshold,
          escalates to Tier 3 (GPT-4o zero-shot). Model loaded via ONNX Runtime
          from MLflow registry at app startup.
Depends:  onnxruntime, transformers, mlflow, numpy
HITL:     None — classification is internal.
"""
