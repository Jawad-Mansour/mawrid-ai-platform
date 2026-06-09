"""
Feature:  WhatsApp Messaging (Wave 1 — deferred from capstone)
Layer:    Infra / Messaging
Module:   app.infra.messaging.whatsapp
Purpose:  Twilio/Meta Business API client for WhatsApp dispatch.
          DEFERRED: WhatsApp is Wave 1 only. In the capstone:
            - B2B communications = email only
            - B2C communications = email + SMS
          This file is a stub. Any call to send() will raise NotImplementedError
          until Wave 1 is activated.
Depends:  twilio (Wave 1)
HITL:     None (Wave 1)
"""
from __future__ import annotations


class WhatsAppClient:
    """Stub client — WhatsApp is deferred to Wave 1."""

    def send(self, to: str, body: str) -> None:
        raise NotImplementedError(
            "WhatsApp is deferred to Wave 1. "
            "Capstone B2B uses email only; B2C uses email + SMS."
        )
