"""
Feature:  NLP Search & RAG Pipeline / AI Agents (cross-cutting)
Layer:    Guardrails / PII
Module:   app.guardrails.presidio
Purpose:  PII redaction using Microsoft Presidio. Strips PII from LLM inputs
          across all features (RAG queries, dunning drafts, agent messages).
          Supports EN / AR / FR via pattern-based recognizers (phone, email,
          credit card, IBAN) that work without NLP models. When spacy models
          are installed (en_core_web_sm, fr_core_news_sm) PERSON and LOCATION
          entities are also detected for EN and FR.
          Runs synchronously (CPU-bound); use async_redact() in async contexts.
Depends:  presidio-analyzer>=2.2.356, presidio-anonymizer>=2.2.356
HITL:     None — guardrails are automated.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Entities detectable via pattern only (no NLP model required)
_PATTERN_ENTITIES = [
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "URL",
]
# Entities that additionally need NLP (spacy)
_NLP_ENTITIES = ["PERSON", "LOCATION", "NRP"]
_ALL_ENTITIES = _PATTERN_ENTITIES + _NLP_ENTITIES

# Replacement tag format: <ENTITY_TYPE>
_OPERATOR_CONFIG: dict[str, Any] = {}  # empty = default Replace operator


# ── Minimal NLP engine stub ──────────────────────────────────────────────────


class _NoopNlpEngine:
    """
    NLP engine that produces no tokens/entities — enables Presidio's pattern
    recognizers (regex-based) without requiring any spacy model installation.
    PERSON and LOCATION detection is disabled in this mode.
    """

    engine_name = "noop"

    def load(self) -> None:
        pass

    def is_loaded(self, language: str | None = None) -> bool:
        return True

    def process_text(self, text: str, language: str) -> Any:
        # Pattern recognizers don't consume NLP artifacts — returning None
        # is sufficient. Typed as Any so mypy doesn't object.
        return None

    def process_batch(
        self, texts: Iterator[tuple[str, Any]], language: str
    ) -> Iterator[tuple[str, Any, Any]]:
        for text, context in texts:
            yield text, context, self.process_text(text, language)

    def get_supported_entities(self) -> list[str]:
        return []

    def get_supported_languages(self) -> list[str]:
        return ["en", "fr", "ar"]


# ── Lazy-init singletons ─────────────────────────────────────────────────────

_analyzer: Any = None
_anonymizer: Any = None


def _get_anonymizer() -> Any:
    global _anonymizer
    if _anonymizer is None:
        from presidio_anonymizer import AnonymizerEngine  # noqa: PLC0415

        _anonymizer = AnonymizerEngine()  # type: ignore[no-untyped-call]
    return _anonymizer


def _build_analyzer_with_spacy() -> Any:
    """Try to build an AnalyzerEngine with spacy EN + FR models."""
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry  # noqa: PLC0415
    from presidio_analyzer.nlp_engine import NlpEngineProvider  # noqa: PLC0415

    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [
                {"lang_code": "en", "model_name": "en_core_web_sm"},
                {"lang_code": "fr", "model_name": "fr_core_news_sm"},
            ],
        }
    )
    nlp_engine = provider.create_engine()
    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(nlp_engine=nlp_engine, languages=["en", "fr"])
    return AnalyzerEngine(
        nlp_engine=nlp_engine,
        registry=registry,
        supported_languages=["en", "fr", "ar"],
    )


def _build_analyzer_pattern_only() -> Any:
    """
    Build an AnalyzerEngine using pattern-only recognizers — no spacy required.
    Detects: PHONE_NUMBER, EMAIL_ADDRESS, CREDIT_CARD, IBAN_CODE, IP_ADDRESS, URL.
    Does NOT detect PERSON or LOCATION (those need NLP models).
    One recognizer instance is added per language per entity type because
    Presidio routes analysis by supported_language (singular), not a list.
    """
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry  # noqa: PLC0415
    from presidio_analyzer.predefined_recognizers import (  # noqa: PLC0415
        CreditCardRecognizer,
        EmailRecognizer,
        IbanRecognizer,
        IpRecognizer,
        PhoneRecognizer,
        UrlRecognizer,
    )

    supported = ["en", "fr", "ar"]
    noop = _NoopNlpEngine()
    # RecognizerRegistry.supported_languages must equal AnalyzerEngine.supported_languages
    registry = RecognizerRegistry(supported_languages=supported)
    for lang in supported:
        for recognizer_cls in (
            PhoneRecognizer,
            EmailRecognizer,
            CreditCardRecognizer,
            IbanRecognizer,
            IpRecognizer,
            UrlRecognizer,
        ):
            import contextlib  # noqa: PLC0415

            with contextlib.suppress(Exception):
                registry.add_recognizer(recognizer_cls(supported_language=lang))
    return AnalyzerEngine(
        nlp_engine=noop,  # type: ignore[arg-type]
        registry=registry,
        supported_languages=supported,
    )


def _get_analyzer() -> Any:
    global _analyzer
    if _analyzer is None:
        try:
            _analyzer = _build_analyzer_with_spacy()
            logger.info("presidio_nlp_full_mode_en_fr")
        except (Exception, SystemExit):
            # spaCy raises SystemExit (not Exception) when a model isn't installed,
            # so catch both to guarantee the pattern-only fallback always engages.
            _analyzer = _build_analyzer_pattern_only()
            logger.warning(
                "presidio_pattern_only_mode "
                "(install en_core_web_sm + fr_core_news_sm for PERSON/LOCATION detection)"
            )
    return _analyzer


# ── Public API ───────────────────────────────────────────────────────────────


@dataclass
class RedactionResult:
    text: str
    was_redacted: bool


def redact(text: str, language: str = "en") -> RedactionResult:
    """
    Analyze text for PII and replace each entity with <ENTITY_TYPE>.
    Runs synchronously — call async_redact() from async contexts.

    Args:
        text:     Input text (may contain PII).
        language: ISO 639-1 code — "en", "fr", or "ar". Defaults to "en".

    Returns:
        RedactionResult with the sanitised text and a flag indicating change.
    """
    if not text or not text.strip():
        return RedactionResult(text=text, was_redacted=False)

    from presidio_anonymizer.entities import OperatorConfig  # noqa: PLC0415

    analyzer = _get_analyzer()
    anonymizer = _get_anonymizer()

    # Presidio may not recognise "ar" if pattern recognizers weren't configured
    # for it — fall back to "en" detection which catches the same regex patterns.
    lang = language if language in ("en", "fr", "ar") else "en"

    try:
        results = analyzer.analyze(text=text, language=lang, entities=_ALL_ENTITIES)
    except Exception:
        # If language detection fails (e.g. no Arabic recognizers), retry with EN
        try:
            results = analyzer.analyze(text=text, language="en", entities=_PATTERN_ENTITIES)
        except Exception:
            logger.exception("presidio_analyze_failed")
            return RedactionResult(text=text, was_redacted=False)

    if not results:
        return RedactionResult(text=text, was_redacted=False)

    operators = {
        entity: OperatorConfig("replace", {"new_value": f"<{entity}>"}) for entity in _ALL_ENTITIES
    }
    anonymized = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
    return RedactionResult(text=anonymized.text, was_redacted=True)


async def async_redact(text: str, language: str = "en") -> RedactionResult:
    """Async wrapper around redact() — safe to call from async routes."""
    return await asyncio.to_thread(redact, text, language)
