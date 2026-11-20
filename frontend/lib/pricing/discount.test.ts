import assert from "node:assert/strict";
import { test } from "node:test";
import {
  formatDiscountBenefit,
  toStoredDiscountValue,
  toUiDiscountValue,
  validateDiscountInput,
} from "./discount.ts";

test("percentage discounts round-trip through basis points", () => {
  assert.equal(toStoredDiscountValue("PERCENTAGE", 20), 2000);
  assert.equal(toUiDiscountValue("PERCENTAGE", 2000), 20);
  assert.equal(formatDiscountBenefit("PERCENTAGE", 2000), "20% OFF");
  assert.equal(formatDiscountBenefit("PERCENTAGE", 1250), "12.5% OFF");
});

test("fixed discounts are stored in paise", () => {
  assert.equal(toStoredDiscountValue("FIXED_AMOUNT", 150), 15000);
  assert.equal(formatDiscountBenefit("FIXED_AMOUNT", 15000), "₹150 OFF");
});

test("validation rejects zero and over-cap percentages", () => {
  assert.ok(validateDiscountInput("PERCENTAGE", 0));
  assert.ok(validateDiscountInput("PERCENTAGE", 95));
  assert.equal(validateDiscountInput("PERCENTAGE", 20), null);
});
