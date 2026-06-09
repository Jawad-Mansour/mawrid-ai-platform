"""
Feature:  AI Agents — Stock Monitor Specialist
Layer:    Agent / Specialist
Module:   app.agents.specialists.stock_monitor_agent
Purpose:  Monitors inventory levels against reorder thresholds. When qty_in_stock
          falls below threshold for a product, creates a purchase_order_send
          HITL action (draft reorder PO for importer approval).
Depends:  langgraph, app.core.procurement.services, app.core.hitl.services
HITL:     purchase_order_send (reorder trigger)
"""
