"""
Feature:  AI Agents — State Persistence
Layer:    Agent
Module:   app.agents.checkpointer
Purpose:  AsyncRedisSaver setup for LangGraph agent state checkpointing.
          thread_id format: {tenant_id}:{user_id}:{session_uuid}. Ensures
          agent conversations survive network interruptions and can be resumed.
          TTL: 24 hours per session.
Depends:  langgraph, redis, app.infra.queue.client (Redis connection)
HITL:     None — state persistence only.
"""
