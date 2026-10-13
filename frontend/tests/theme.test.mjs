import assert from "node:assert/strict";
import test from "node:test";

import { setupThemeToggle, THEME_STORAGE_KEY } from "../js/theme.mjs";

function createButton() {
  const attributes = {};
  const listeners = {};
  return {
    attributes,
    listeners,
    textContent: "",
    setAttribute(name, value) {
      attributes[name] = value;
    },
    addEventListener(name, callback) {
      listeners[name] = callback;
    },
    click() {
      listeners.click();
    },
  };
}

function createStorage(initialValue = null) {
  const values = new Map(initialValue ? [[THEME_STORAGE_KEY, initialValue]] : []);
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

test("restores the saved theme and persists toggle changes for the next load", () => {
  const storage = createStorage("dark");
  const root = { dataset: {} };
  const button = createButton();

  setupThemeToggle(root, button, storage);
  assert.equal(root.dataset.theme, "dark");
  assert.equal(button.attributes["aria-pressed"], "true");
  assert.equal(button.textContent, "라이트 모드");

  button.click();
  assert.equal(root.dataset.theme, "light");
  assert.equal(storage.getItem(THEME_STORAGE_KEY), "light");

  const reloadedRoot = { dataset: {} };
  setupThemeToggle(reloadedRoot, createButton(), storage);
  assert.equal(reloadedRoot.dataset.theme, "light");
});

test("defaults to light mode and continues working when storage is unavailable", () => {
  const root = { dataset: {} };
  const button = createButton();
  const blockedStorage = {
    getItem() { throw new Error("storage unavailable"); },
    setItem() { throw new Error("storage unavailable"); },
  };

  setupThemeToggle(root, button, blockedStorage);
  assert.equal(root.dataset.theme, "light");
  assert.doesNotThrow(() => button.click());
  assert.equal(root.dataset.theme, "dark");
});
