#!/usr/bin/env bash
# Feature audit: runs the API test files that cover each marketplace feature
# and prints one pass/fail line per feature. Uses the isolated *_test database
# (see backend/tests/conftest.py); never touches basket_db.
set -uo pipefail
cd "$(dirname "$0")/../backend"
unset DATABASE_URL
export BASKET_TEST_SKIP_MIGRATE="${BASKET_TEST_SKIP_MIGRATE:-0}"

declare -a AREAS=(
  "Authentication & role redirects|tests/test_identity.py tests/test_multi_role_portals.py tests/test_mc_e2e_journeys.py::test_journey_b_retailer_onboarding_to_selling"
  "Customer-only checkout (role isolation)|tests/test_mc_e2e_journeys.py::test_journey_f_role_isolation tests/test_cart.py tests/test_quotes.py"
  "Retailer onboarding & approval|tests/test_mc_retailer_onboarding.py::test_onboarding_pending_documents_approval tests/test_admin_marketplace_moderation.py"
  "Product creation & image uploads|tests/test_retailer_listings_inventory.py tests/test_mc_retailer_onboarding.py::test_listing_and_canonical_image_uploads tests/test_catalogue.py"
  "Inventory updates & reservations|tests/test_reservations.py tests/test_marketplace_authenticity_and_inventory.py"
  "Order fulfilment (payment-gated) & payments|tests/test_mc_commerce_integrity.py tests/test_mc_e2e_journeys.py::test_journey_a_customer_purchase_to_delivery tests/test_payments.py tests/test_orders.py tests/test_orders_postpurchase.py"
  "Admin governance & audit log|tests/test_mc_governance.py tests/test_mc_e2e_journeys.py::test_journey_c_admin_suspends_and_reinstates_customer tests/test_mc_data_quarantine.py"
  "Community buying (3B)|tests/test_p3_community_buying.py tests/test_mc_phase3_completion.py tests/test_mc_e2e_journeys.py::test_journey_d_customer_group_buy"
  "RFQs / Community Exchange (3C)|tests/test_p3_community_exchange.py"
  "Dukaan vs Dukaan (3E)|tests/test_p3_dukaan_vs_dukaan.py"
  "AI Negotiator (3D) & deal assistant|tests/test_p3_negotiator.py tests/test_mc_assistant.py"
  "Price Intelligence & Sale Stream (3F/3G)|tests/test_p3_price_intel_sale_stream.py"
  "Demand Gap (3A)|tests/test_p3_demand_gap.py"
  "OCR / manual fallback (3I)|tests/test_p3_vision_list.py"
  "Multilingual (3H)|tests/test_p3_multilingual.py tests/test_mc_e2e_journeys.py::test_journey_e_language_preference_persists"
  "Missions, substitutes, intent, passport (Phase 2)|tests/test_basket_mission.py tests/test_substitute_intelligence.py tests/test_intent_memory.py tests/test_product_passport.py"
)

FAIL=0
printf '%-48s %s\n' "AREA" "RESULT"
for entry in "${AREAS[@]}"; do
  name="${entry%%|*}"; files="${entry#*|}"
  # shellcheck disable=SC2086
  line="$(.venv/bin/python -m pytest -q -p no:cacheprovider $files 2>&1 | tail -1)"
  [[ "$line" == *failed* || "$line" == *error* ]] && FAIL=1
  printf '%-48s %s\n' "$name" "$line"
  export BASKET_TEST_SKIP_MIGRATE=1
done
exit $FAIL
