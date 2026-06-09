"""
Feature:  AI Chatbot — Intent Classifier Training Data
Layer:    Scripts / Data Generation
Module:   scripts.generate_intent_data
Purpose:  Generates 1200+ labeled intent training examples (150 per class,
          8 classes): product_search, order_status, stock_check,
          shipment_status, invoice_query, dunning_action, complex_task,
          out_of_scope. Arabic + English + French for Lebanese market.
          Saves train split (80%) to intent_training_data.json and
          held-out test split (20%) to intent_test_set.json.
          Run with: uv run python scripts/generate_intent_data.py
Depends:  None (stdlib only)
HITL:     None.
"""
import json
import random
from pathlib import Path

TEMPLATES: dict[str, list[str]] = {
    "product_search": [
        "Show me all {category} products",
        "Do you have {product}?",
        "What {category} do you carry?",
        "I'm looking for {product}",
        "Find me {category} items",
        "عندكم {product}؟",
        "أريد {category}",
        "شو عندكم من {category}؟",
        "Avez-vous des {category}?",
        "Je cherche {product}",
        "Search catalog for {product}",
        "List all available {category}",
    ],
    "order_status": [
        "What's the status of order {order_id}?",
        "Where is my order {order_id}?",
        "Track order {order_id}",
        "Has order {order_id} shipped?",
        "Update on purchase order {order_id}",
        "وين طلبيتي {order_id}؟",
        "شو صار بالأوردر {order_id}؟",
        "Quel est le statut de la commande {order_id}?",
        "how many did I order in {order_id}?",
        "Is {order_id} confirmed?",
        "Show me PO {order_id}",
    ],
    "stock_check": [
        "How many units of {product} do I have?",
        "What's my current inventory of {product}?",
        "Is {product} in stock?",
        "Check availability of {product}",
        "What's the stock level for {product}?",
        "كم قطعة عندي من {product}؟",
        "هل يوجد {product} في المخزن؟",
        "Combien d'unités de {product} ai-je?",
        "how many do I have of {product}?",
        "Current quantity of {product}",
        "Inventory count for {product}",
    ],
    "shipment_status": [
        "Where is my {product} shipment?",
        "When does the container with {product} arrive?",
        "What's the ETA for my {category} delivery?",
        "Has the shipment for {order_id} left port?",
        "Track my container for {product}",
        "وين الشحنة تبعت {product}؟",
        "امتى بتوصل بضاعة {category}؟",
        "Où est mon expédition de {product}?",
        "Shipment update for {order_id}",
        "Is the {product} delivery on schedule?",
    ],
    "invoice_query": [
        "Which invoices are overdue?",
        "Show me unpaid B2B invoices",
        "What's the balance on invoice {invoice_id}?",
        "List all outstanding invoices",
        "Has invoice {invoice_id} been paid?",
        "شو الفواتير اللي مو مدفوعة؟",
        "شو رصيد فاتورة {invoice_id}؟",
        "Quelles factures sont en retard?",
        "Show me invoices due this month",
        "Invoice aging report",
        "Total unpaid amount from {invoice_id}",
    ],
    "dunning_action": [
        "Stop dunning on invoice {invoice_id}",
        "Manually trigger Track 3 for invoice {invoice_id}",
        "Pause collections for {invoice_id}",
        "Send an immediate reminder for {invoice_id}",
        "Cancel the dunning sequence for {invoice_id}",
        "وقف التحصيل على فاتورة {invoice_id}",
        "ابعث تذكير فوري لفاتورة {invoice_id}",
        "Arrêter les relances pour {invoice_id}",
        "Escalate dunning for {invoice_id}",
        "Which invoices are in active dunning?",
    ],
    "complex_task": [
        "Find me a new {category} supplier and draft an outreach email",
        "Analyze our top suppliers and recommend which to reorder from",
        "Create a purchase order for {product} and notify the supplier",
        "Find low stock items and draft reorder requests for all",
        "Review overdue invoices and start dunning sequences for all",
        "ابحث عن مورد جديد ل{category} وحضر رسالة تواصل",
        "Cherche un nouveau fournisseur de {category} et rédige un email",
        "Check all shipments arriving this week and prepare receiving forms",
        "Audit our inventory and flag products below reorder threshold",
        "Generate a supplier performance report and score all suppliers",
    ],
    "out_of_scope": [
        "What's the weather today?",
        "Write me a poem",
        "Who won the World Cup?",
        "Tell me a joke",
        "What time is it?",
        "شو الطقس اليوم؟",
        "احكيلي نكتة",
        "Quel temps fait-il?",
        "Hello",
        "Thanks",
        "مرحبا",
        "شكراً",
        "Never mind",
        "OK",
    ],
}

PRODUCTS = [
    "Nescafe 200g", "Ariel 2kg", "Baraka water 500ml", "Maggi noodles",
    "Tide detergent", "Dove soap", "LG refrigerator", "Samsung TV 55in",
    "Bosch washing machine", "Heinz ketchup 500ml",
]
CATEGORIES = [
    "cleaning products", "food items", "beverages", "personal care",
    "appliances", "dairy", "frozen food", "electronics",
]
ORDER_IDS = [f"PO-2025-{i:04d}" for i in range(1, 25)]
INVOICE_IDS = [f"INV-2025-{i:03d}" for i in range(1, 25)]


def fill_template(template: str) -> str:
    return (
        template
        .replace("{product}", random.choice(PRODUCTS))
        .replace("{category}", random.choice(CATEGORIES))
        .replace("{order_id}", random.choice(ORDER_IDS))
        .replace("{invoice_id}", random.choice(INVOICE_IDS))
    )


def generate_examples(per_class: int = 150, seed: int = 42) -> list[dict]:
    random.seed(seed)
    examples: list[dict] = []
    idx = 1

    for intent, templates in TEMPLATES.items():
        count = 0
        while count < per_class:
            template = random.choice(templates)
            text = fill_template(template)
            examples.append({
                "id": f"it-{idx:04d}",
                "text": text,
                "intent": intent,
                "source": "synthetic",
                "language": "arabic" if any(ord(c) > 0x0600 for c in text) else "english",
            })
            idx += 1
            count += 1

    random.shuffle(examples)
    return examples


if __name__ == "__main__":
    examples = generate_examples()

    counts: dict[str, int] = {}
    for e in examples:
        counts[e["intent"]] = counts.get(e["intent"], 0) + 1
    print(f"Generated {len(examples)} examples: {counts}")

    out_dir = (
        Path(__file__).parent.parent
        / "backend" / "tests" / "evals" / "eval_dataset"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    # 80/20 split — held-out test set used by CI Gate 8
    split = int(len(examples) * 0.8)
    train = examples[:split]
    test = examples[split:]

    (out_dir / "intent_training_data.json").write_text(json.dumps(train, indent=2))
    (out_dir / "intent_test_set.json").write_text(json.dumps(test, indent=2))

    print(f"Train: {len(train)} examples → intent_training_data.json")
    print(f"Test:  {len(test)} examples → intent_test_set.json")
