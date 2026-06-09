"""
Feature:  Dunning Engine (4 Tracks)
Layer:    API / Router
Module:   app.api.dunning
Purpose:  HTTP routes for dunning sequence management: list active sequences,
          manually trigger a track, stop a sequence, view track history.
          Scheduled triggers are fired by n8n WF-09 through WF-15.
Depends:  app.core.dunning.services, app.api.deps
HITL:     All dunning action_types (payables_advance, disputes_on_demand,
          receivables_day7/14/21, b2c_day3/7/14)
"""
from fastapi import APIRouter

router = APIRouter(prefix="/dunning", tags=["dunning"])
