"""
Feature:  AI Agents — Communication Specialist
Layer:    Agent / Specialist
Module:   app.agents.specialists.communication_agent
Purpose:  Drafts all outbound communications: supplier outreach emails, purchase
          order documents, dispute letters, and dunning messages (tone-classified).
          EVERY draft is submitted as a HITL action — Communication Agent never
          sends directly.
Depends:  langgraph, app.core.hitl.services, app.core.dunning.tone_classifier,
          app.infra.llm.openai_client
HITL:     All action_types that involve sending to external parties.
"""
