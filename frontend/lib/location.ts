/** Delivery pincode chosen by the shopper (stored on this device only). */
const KEY = "basket.pincode";
export const PINCODE_EVENT = "basket:pincode";

export function isValidPincode(v: string): boolean {
  return /^[1-9][0-9]{5}$/.test(v.trim());
}

export function getPincode(): string | null {
  try {
    const v = window.localStorage.getItem(KEY);
    return v && isValidPincode(v) ? v : null;
  } catch {
    return null;
  }
}

export function setPincode(v: string | null): void {
  try {
    if (v) window.localStorage.setItem(KEY, v);
    else window.localStorage.removeItem(KEY);
    window.dispatchEvent(new CustomEvent(PINCODE_EVENT, { detail: v }));
  } catch {
    /* ignore */
  }
}
