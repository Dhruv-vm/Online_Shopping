import assert from "node:assert/strict";
import { test } from "node:test";
import { DICTIONARIES, missingKeys, translate } from "./dictionaries.ts";
import { LANGUAGES, isLanguageCode, languageMeta, type LanguageCode } from "./languages.ts";
import { formatMoney } from "./format.ts";
import CORE_KEYS from "../../locales/core-keys.json" with { type: "json" };

const CODES = LANGUAGES.map((l) => l.code) as LanguageCode[];
const PLACEHOLDER = /\{\w+\}/g;

/** Keys every language must translate: navigation, auth, statuses, errors, validation, portals. */
const coreKeys: string[] = CORE_KEYS;

test("all twelve languages are registered and load a dictionary", () => {
  assert.equal(CODES.length, 12);
  for (const c of ["en", "hi", "kn", "ta", "te", "ml", "bn", "mr", "gu", "pa", "or", "ur"]) {
    assert.ok(isLanguageCode(c), c);
    assert.ok(Object.keys(DICTIONARIES[c as LanguageCode]).length > 0, `${c} dictionary is empty`);
  }
  assert.equal(languageMeta("ur").dir, "rtl");
  assert.equal(languageMeta("hi").dir, "ltr");
  assert.ok(!isLanguageCode("xx"));
});

test("every language translates the core interface keys", () => {
  assert.ok(coreKeys.length >= 290, "core key set unexpectedly small");
  for (const k of coreKeys) assert.ok(k in DICTIONARIES.en, `core key ${k} missing from English`);
  for (const c of CODES) {
    const missing = coreKeys.filter((k) => !(k in DICTIONARIES[c]));
    assert.deepEqual(missing, [], `${c} is missing core keys`);
  }
});

test("translations never copy English verbatim for core labels", () => {
  // Brand names and codes are allowed to stay as-is.
  const allowSame = /^(BASKET|MRP|GSTIN|Razorpay|\{.*\}|[\d\W]+)$/;
  for (const c of CODES.filter((c) => c !== "en")) {
    const same = coreKeys.filter((k) => DICTIONARIES[c][k] === DICTIONARIES.en[k] && !allowSame.test(DICTIONARIES.en[k]));
    assert.ok(same.length <= 3, `${c} copies English for: ${same.join(", ")}`);
  }
});

test("placeholders are preserved in every translation", () => {
  for (const c of CODES) {
    for (const [k, v] of Object.entries(DICTIONARIES[c])) {
      const en = DICTIONARIES.en[k];
      assert.ok(en !== undefined, `${c} has key ${k} not present in English`);
      assert.deepEqual((v.match(PLACEHOLDER) ?? []).sort(), (en.match(PLACEHOLDER) ?? []).sort(), `${c}:${k}`);
    }
  }
});

test("missing keys fall back to English, then to the key", () => {
  assert.equal(translate("hi", "nav.cart"), DICTIONARIES.hi["nav.cart"]);
  const fallbackKey = missingKeys("hi")[0];
  if (fallbackKey) assert.equal(translate("hi", fallbackKey), DICTIONARIES.en[fallbackKey]);
  assert.equal(translate("kn", "no.such.key"), "no.such.key");
  assert.equal(translate("en", "common.onlyLeft", { n: 3 }), DICTIONARIES.en["common.onlyLeft"].replace("{n}", "3"));
  assert.ok(translate("ta", "common.onlyLeft", { n: 7 }).includes("7"));
});

test("currency is formatted as Indian rupees in every locale", () => {
  for (const c of CODES) {
    const s = formatMoney(123450, c);
    assert.ok(s.length > 0, c);
  }
  assert.match(formatMoney(12345600, "en"), /₹\s?1,23,456/);
});

test("coverage report", () => {
  const total = Object.keys(DICTIONARIES.en).length;
  const report = CODES.map((c) => `${c} ${Math.round((100 * (total - missingKeys(c).length)) / total)}%`);
  console.log(`i18n coverage of ${total} keys: ${report.join(" · ")}`);
});
