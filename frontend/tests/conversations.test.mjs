import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const appSource = await readFile(new URL("../js/app.js", import.meta.url), "utf8");
const sourceWithoutImports = appSource.replace(
  /^import\s+[\s\S]*?\sfrom\s+["'][^"']+["'];\s*/gm,
  "",
);

class FakeElement {
  constructor(tagName = "div", { fragment = false } = {}) {
    this.tagName = tagName.toUpperCase();
    this.isFragment = fragment;
    this.children = [];
    this.parentElement = null;
    this.dataset = {};
    this.attributes = {};
    this.listeners = new Map();
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.checked = false;
    this.className = "";
    this._text = "";
    const classes = new Set();
    this.classList = {
      toggle: (name, force) => {
        const enabled = force ?? !classes.has(name);
        enabled ? classes.add(name) : classes.delete(name);
        return enabled;
      },
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      contains: (name) => classes.has(name),
    };
  }

  set textContent(value) {
    this._text = String(value ?? "");
    this.children = [];
  }

  get textContent() {
    return this._text + this.children.map((child) => child.textContent).join("");
  }

  append(...items) {
    for (const item of items) {
      if (item?.isFragment) {
        this.append(...item.children);
        item.children = [];
      } else {
        if (item && typeof item === "object") item.parentElement = this;
        this.children.push(item);
      }
    }
  }

  replaceChildren(...items) {
    this.children = [];
    this._text = "";
    this.append(...items);
  }

  addEventListener(name, callback) {
    this.listeners.set(name, callback);
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  removeAttribute(name) {
    delete this.attributes[name];
  }

  contains(candidate) {
    return this.children.some(
      (child) => child === candidate || child?.contains?.(candidate),
    );
  }

  closest(selector) {
    if (
      selector === "button[data-action][data-conversation-id]" &&
      this.tagName === "BUTTON" &&
      this.dataset.action &&
      this.dataset.conversationId
    ) {
      return this;
    }
    return null;
  }

  querySelectorAll(selector) {
    const matches = [];
    const visit = (node) => {
      for (const child of node.children) {
        if (
          selector === 'button[data-action="select"][data-conversation-id]' &&
          child.tagName === "BUTTON" &&
          child.dataset.action === "select" &&
          child.dataset.conversationId
        ) {
          matches.push(child);
        }
        visit(child);
      }
    };
    visit(this);
    return matches;
  }
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

async function waitFor(predicate) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (predicate()) return;
    await new Promise((resolve) => setImmediate(resolve));
  }
  assert.fail("UI state did not settle within the test window");
}

function createHarness({ getConversations, getConversation }) {
  const ids = [...sourceWithoutImports.matchAll(/getRequiredElement\("([^"]+)"\)/g)]
    .map((match) => match[1]);
  const elementsById = new Map(ids.map((id) => [id, new FakeElement("div")]));
  const document = {
    readyState: "complete",
    documentElement: new FakeElement("html"),
    getElementById: (id) => elementsById.get(id) ?? null,
    createElement: (tagName) => new FakeElement(tagName),
    createDocumentFragment: () => new FakeElement("fragment", { fragment: true }),
    createTextNode: (text) => {
      const node = new FakeElement("#text");
      node._text = String(text);
      return node;
    },
    addEventListener() {},
  };

  const injected = {
    createData: async () => {},
    deleteConversation: async () => {},
    deleteData: async () => {},
    getConversation,
    getConversations,
    getData: async () => [],
    getDataSummary: async () => ({ total_count: 0 }),
    sendChatMessage: async () => {},
    updateData: async () => {},
    renderTrendChart: () => {},
    serializeTrendDataJson: () => "[]",
    TREND_KEYWORDS: ["keyword-a", "keyword-b", "keyword-c"],
    setupThemeToggle: () => {},
  };
  const names = Object.keys(injected);
  const factory = vm.runInNewContext(
    `(function(${names.join(",")}) { ${sourceWithoutImports}\nreturn {elements, loadConversations, loadConversation, handleConversationListClick}; })`,
    { document, window: { localStorage: {} }, console, URL, Blob, Intl, Map, Set },
  );
  const app = factory(...names.map((name) => injected[name]));
  return { ...app, elements: app.elements, elementsById };
}

function createConversationFixture() {
  return {
    id: "fixture-conversation-1",
    title: "테스트 대화",
    messages: [
      { role: "user", content: "합성 질문입니다.", created_at: "2026-10-01T00:00:00Z" },
      { role: "assistant", content: "합성 답변입니다.", created_at: "2026-10-01T00:00:01Z" },
    ],
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:01Z",
  };
}

function fixtureList(conversation) {
  return [{
    id: conversation.id,
    title: conversation.title,
    message_count: conversation.messages.length,
    created_at: conversation.created_at,
    updated_at: conversation.updated_at,
  }];
}

function selectButton(harness, id) {
  return harness.elements.conversationList
    .querySelectorAll('button[data-action="select"][data-conversation-id]')
    .find((button) => button.dataset.conversationId === id);
}

test("loads a conversation list after initialization, selects by ID, and renders both messages", async () => {
  const conversation = createConversationFixture();
  const listCalls = [];
  const detailCalls = [];
  const harness = createHarness({
    getConversations: async () => {
      listCalls.push("called");
      return fixtureList(conversation);
    },
    getConversation: async (id) => {
      detailCalls.push(id);
      return conversation;
    },
  });

  await waitFor(() => Boolean(selectButton(harness, conversation.id)));
  assert.equal(listCalls.length, 1);
  assert.equal(harness.elements.conversationsLoading.hidden, true);
  assert.equal(harness.elements.conversationsError.hidden, true);

  const button = selectButton(harness, conversation.id);
  harness.handleConversationListClick({ target: button });
  await waitFor(() => harness.elements.chatLoading.hidden &&
    harness.elements.chatMessages.children.length === 2);

  assert.deepEqual(detailCalls, [conversation.id]);
  assert.equal(harness.elements.activeConversationTitle.textContent, conversation.title);
  assert.deepEqual(
    harness.elements.chatMessages.children.map((message) => message.dataset.role),
    ["user", "assistant"],
  );
  assert.equal(harness.elements.chatMessages.children[0].textContent.includes("합성 질문입니다."), true);
  assert.equal(harness.elements.chatMessages.children[1].textContent.includes("합성 답변입니다."), true);
  assert.equal(harness.elements.chatEmpty.hidden, true);
});

test("reinitializing after reload fetches the list again and restores the selected conversation", async () => {
  const conversation = createConversationFixture();
  let listCalls = 0;
  const makeReloadedPage = () => createHarness({
    getConversations: async () => {
      listCalls += 1;
      return fixtureList(conversation);
    },
    getConversation: async (id) => {
      assert.equal(id, conversation.id);
      return conversation;
    },
  });

  const firstLoad = makeReloadedPage();
  await waitFor(() => Boolean(selectButton(firstLoad, conversation.id)));
  const reloadedPage = makeReloadedPage();
  await waitFor(() => Boolean(selectButton(reloadedPage, conversation.id)));
  assert.equal(listCalls, 2);

  reloadedPage.handleConversationListClick({ target: selectButton(reloadedPage, conversation.id) });
  await waitFor(() => reloadedPage.elements.chatLoading.hidden &&
    reloadedPage.elements.chatMessages.children.length === 2);
  assert.deepEqual(
    reloadedPage.elements.chatMessages.children.map((message) => message.dataset.role),
    ["user", "assistant"],
  );
});

test("shows loading while detail is pending and hides it after successful restoration", async () => {
  const conversation = createConversationFixture();
  const detail = deferred();
  const harness = createHarness({
    getConversations: async () => fixtureList(conversation),
    getConversation: () => detail.promise,
  });
  await waitFor(() => Boolean(selectButton(harness, conversation.id)));

  const pendingLoad = harness.loadConversation(conversation.id);
  assert.equal(harness.elements.chatLoading.hidden, false);
  detail.resolve(conversation);
  await pendingLoad;

  assert.equal(harness.elements.chatLoading.hidden, true);
  assert.equal(harness.elements.chatError.hidden, true);
  assert.equal(harness.elements.chatMessages.children.length, 2);
});

test("shows conversation-list loading while its fake response is pending", async () => {
  const conversation = createConversationFixture();
  const list = deferred();
  const harness = createHarness({
    getConversations: () => list.promise,
    getConversation: async () => conversation,
  });

  assert.equal(harness.elements.conversationsLoading.hidden, false);
  list.resolve(fixtureList(conversation));
  await waitFor(() => Boolean(selectButton(harness, conversation.id)));

  assert.equal(harness.elements.conversationsLoading.hidden, true);
  assert.equal(harness.elements.conversationsError.hidden, true);
});

test("shows a detail error and clears loading when retrieval fails", async () => {
  const conversation = createConversationFixture();
  const harness = createHarness({
    getConversations: async () => fixtureList(conversation),
    getConversation: async () => { throw new Error("fake detail failure"); },
  });
  await waitFor(() => Boolean(selectButton(harness, conversation.id)));

  await harness.loadConversation(conversation.id);

  assert.equal(harness.elements.chatLoading.hidden, true);
  assert.equal(harness.elements.chatError.hidden, false);
  assert.equal(harness.elements.chatError.textContent, "대화를 불러오지 못했습니다.");
});

test("shows the empty state for a conversation with no messages", async () => {
  const conversation = { ...createConversationFixture(), messages: [] };
  const harness = createHarness({
    getConversations: async () => fixtureList(conversation),
    getConversation: async () => conversation,
  });
  await waitFor(() => Boolean(selectButton(harness, conversation.id)));

  await harness.loadConversation(conversation.id);

  assert.equal(harness.elements.chatMessages.children.length, 0);
  assert.equal(harness.elements.chatEmpty.hidden, false);
  assert.equal(harness.elements.chatLoading.hidden, true);
});

test("shows a conversation-list error and clears its loading indicator", async () => {
  const harness = createHarness({
    getConversations: async () => { throw new Error("fake list failure"); },
    getConversation: async () => createConversationFixture(),
  });

  await waitFor(() => harness.elements.conversationsLoading.hidden &&
    !harness.elements.conversationsError.hidden);

  assert.equal(harness.elements.conversationList.children.length, 0);
  assert.equal(harness.elements.conversationsError.textContent, "대화 목록을 불러오지 못했습니다.");
});
