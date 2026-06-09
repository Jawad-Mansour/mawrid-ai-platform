"""
Feature:  Dunning Engine — Tone Classifier
Layer:    ML / Tone
Module:   app.ml.tone.trainer
Purpose:  Training script for tone classifier. Consumes labeled tone dataset
          from scripts/generate_tone_data.py (240 examples, 80 per class,
          deterministic rules). Applies SMOTE oversampling, trains sklearn
          classifier (random_state=42), serializes to backend/ml_models/.
Depends:  scikit-learn, imbalanced-learn
HITL:     None.
"""
