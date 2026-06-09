"""
Feature:  Dunning Engine — Tone Classifier
Layer:    Tests / Unit
Module:   tests.unit.test_tone_classifier
Purpose:  Unit tests for tone classifier priority rules (before ML model).
          Verifies: days_overdue > 21 → firm (rule), prior_disputes > 0 AND
          days_overdue < 7 → neutral (rule), within normal range → ML model fallback.
Depends:  app.core.dunning.tone_classifier
HITL:     None.
"""
