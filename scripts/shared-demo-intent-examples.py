"""Runs the three intent examples from BASKET_INTENT_DEMO_GUIDE.md against the shared demo."""
import json, sys
import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3100"
c = httpx.Client(base_url=BASE, timeout=60)
c.post("/api/v1/auth/login", json={"email": "customer@basket.demo", "password": "Basket@123"}).raise_for_status()
c.headers["X-CSRF-Token"] = c.cookies.get("XSRF-TOKEN", "")
PIN = sys.argv[2] if len(sys.argv) > 2 else "560034"
EXAMPLES = {
    "A": {"title": "Monthly groceries", "frequency": "MONTHLY", "budget_paise": 400000, "pincode": PIN,
          "items": [{"name": "Rice", "quantity": 1}, {"name": "Atta", "quantity": 1},
                    {"name": "Cooking oil", "quantity": 1}, {"name": "Dal", "quantity": 2}]},
    "B": {"title": "New laptop", "frequency": "ONCE", "budget_paise": 6000000, "pincode": PIN, "purchase_by": "2026-12-31",
          "items": [{"name": "Laptop", "quantity": 1, "specs": "16GB RAM, 512GB SSD, for work"}]},
    "C": {"title": "Standing desk", "frequency": "ONCE", "pincode": PIN,
          "items": [{"name": "Electric standing desk", "quantity": 1}]},
}
for k, body in EXAMPLES.items():
    r = c.post("/api/v1/intent/workflow", json=body)
    j = r.json()
    print(f"== Example {k}: HTTP {r.status_code} status={j.get('status')} updated_existing={j.get('updated_existing')} "
          f"cheapest={j.get('cheapest_total_paise')} within_budget={j.get('within_budget')} basket={j.get('can_create_basket')}")
    for it in j.get("items", []):
        m = it["matches"][0] if it["matches"] else None
        print(f"   {it['quantity']}x {it['understood_as']} -> {it['status']} stores={it['retailer_count']} cat={it['category']}"
              + (f" | best: {m['product_name']} @ {m['retailer_name']} ₹{m['price_paise']/100:.2f} offers={m['offers']}" if m else "")
              + (f" | demand: {it['demand']['unique_customers']}/{it['demand']['visibility_threshold']} recorded_now={it['demand']['signal_recorded_now']}" if it['demand'] else ""))
    print("   next:", json.dumps(j.get("next_steps"), ensure_ascii=False)[:400])
    print("   id:", j.get("intention", {}).get("id"))
