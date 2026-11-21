/**
 * Discount value conventions shared with the backend pricing engine.
 *
 * - PERCENTAGE discounts are stored in basis points (1% = 100 bps, max 9000 = 90%).
 * - FIXED_AMOUNT discounts are stored in paise (₹1 = 100 paise).
 *
 * Every screen that creates, edits or displays a discount must use these helpers
 * so the UI and the checkout calculation always agree.
 */
export type DiscountType = "PERCENTAGE" | "FIXED_AMOUNT";

export const MAX_PERCENT = 90;

export function toStoredDiscountValue(type: DiscountType, uiValue: number): number {
  return Math.round(uiValue * 100);
}

export function toUiDiscountValue(type: DiscountType, storedValue: number): number {
  return storedValue / 100;
}

export function formatPercent(bps: number): string {
  const pct = bps / 100;
  return Number.isInteger(pct) ? `${pct}%` : `${pct.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}%`;
}

export function formatDiscountBenefit(type: DiscountType | string, storedValue: number): string {
  if (type === "PERCENTAGE") return `${formatPercent(storedValue)} OFF`;
  const rupees = storedValue / 100;
  return `₹${Number.isInteger(rupees) ? rupees.toLocaleString("en-IN") : rupees.toFixed(2)} OFF`;
}

export function validateDiscountInput(type: DiscountType, uiValue: number): string | null {
  if (!Number.isFinite(uiValue) || uiValue <= 0) return "Discount must be greater than zero.";
  if (type === "PERCENTAGE" && uiValue > MAX_PERCENT)
    return `Percentage discount cannot exceed ${MAX_PERCENT}%.`;
  return null;
}
