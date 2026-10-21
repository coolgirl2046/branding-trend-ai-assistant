import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { createConfig } = require("../scripts/build-config.cjs");
test("build config uses the deployment environment URL", () => {
  const output = createConfig("https://api.example.com/");
  assert.match(output, /https:\/\/api.example.com/);
  assert.ok(!output.includes("onrender.com"));
});
test("missing API URL fails the deployment build", () => {
  assert.throws(() => createConfig(""), /API_BASE_URL/);
});
test("credentials and unsafe URL schemes are rejected", () => {
  for (const url of ["file:///tmp/a", "https://user:secret@example.com", "https://example.com/?key=secret"]) {
    assert.throws(() => createConfig(url));
  }
});
