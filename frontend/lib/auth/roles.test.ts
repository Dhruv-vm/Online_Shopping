import assert from "node:assert/strict";
import { test } from "node:test";
import { canShop, homeForRole, postLoginDestination } from "./roles.ts";

test("each verified role lands on its own home", () => {
  assert.equal(homeForRole("customer"), "/");
  assert.equal(homeForRole("retailer"), "/retailer");
  assert.equal(homeForRole("admin"), "/admin");
});

test("redirects never cross role boundaries or leave the site", () => {
  assert.equal(postLoginDestination("customer", "/admin/users"), "/");
  assert.equal(postLoginDestination("customer", "/retailer/orders"), "/");
  assert.equal(postLoginDestination("customer", "/retailers"), "/retailers");
  assert.equal(postLoginDestination("retailer", "/checkout"), "/retailer");
  assert.equal(postLoginDestination("retailer", "/retailer/orders"), "/retailer/orders");
  assert.equal(postLoginDestination("admin", "//evil.example"), "/admin");
  assert.equal(postLoginDestination("customer", "/cart"), "/cart");
  assert.equal(postLoginDestination("admin", "/login"), "/admin");
});

test("only customers and guests can shop", () => {
  assert.ok(canShop(undefined));
  assert.ok(canShop("customer"));
  assert.ok(!canShop("retailer"));
  assert.ok(!canShop("admin"));
});
