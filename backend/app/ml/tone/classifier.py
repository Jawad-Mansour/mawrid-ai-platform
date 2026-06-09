"""
Feature:  Dunning Engine — Tone Classifier
Layer:    ML / Tone
Module:   app.ml.tone.classifier
Purpose:  3-class tone classification (gentle / neutral / firm) for dunning
          messages. Features: days_overdue, amount_due, prior_disputes,
          payment_history_score, customer_segment. Priority-ordered rules
          applied first; ML model (sklearn, SMOTE, random_state=42) for
          ambiguous cases. Loaded at startup, inference < 1ms.
Depends:  scikit-learn, imbalanced-learn (SMOTE)
HITL:     None — classification is internal.
"""
