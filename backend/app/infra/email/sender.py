"""
Feature:  Dunning Engine / Procurement / Storefront (cross-cutting)
Layer:    Infra / Email
Module:   app.infra.email.sender
Purpose:  Email client (SendGrid). Sends: dunning messages (Tracks 1-4),
          purchase orders to suppliers, fulfillment notifications to consumers,
          and invoice PDF attachments. All sends happen after HITL approval —
          this module is called only from HITL action execution paths.
          B2B: email only in capstone (WhatsApp in Wave 1).
          B2C: email + SMS in capstone (WhatsApp in Wave 1).
Depends:  sendgrid (or httpx for SES), app.infra.secrets.vault
HITL:     None — this IS the execution layer called after HITL approval.
"""
