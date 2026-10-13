import assert from "node:assert/strict";
import test from "node:test";

import {
  buildTrendSeries,
  renderTrendChart,
  serializeTrendDataJson,
  TREND_KEYWORDS,
} from "../js/bonus_features.mjs";

const records = [
  { id: "b2", date: "2026-06-08", keyword: "스피치", value: 40, memo: null },
  { id: "a2", date: "2026-06-08", keyword: "퍼스널브랜딩", value: 20, memo: "주간" },
  { id: "c1", date: "2026-06-01", keyword: "이미지메이킹", value: 10, memo: null },
  { id: "c2", date: "2026-06-08", keyword: "이미지메이킹", value: 15, memo: null },
  { id: "a1", date: "2026-06-01", keyword: "퍼스널브랜딩", value: 18, memo: null },
  { id: "b1", date: "2026-06-01", keyword: "스피치", value: 35, memo: null },
];

class FakeElement {
  constructor(name) {
    this.name = name;
    this.children = [];
    this.attributes = {};
    this.className = "";
    this.textContent = "";
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  append(...children) {
    this.children.push(...children);
  }

  replaceChildren(...children) {
    this.children = children;
  }
}

const fakeDocument = {
  createElement: (name) => new FakeElement(name),
  createElementNS: (_namespace, name) => new FakeElement(name),
};

function descendants(node, name) {
  return node.children.flatMap((child) => [
    ...(child.name === name ? [child] : []),
    ...descendants(child, name),
  ]);
}

test("builds three chronologically ordered keyword series from Firebase records", () => {
  const result = buildTrendSeries(records);

  assert.deepEqual(result.dates, ["2026-06-01", "2026-06-08"]);
  assert.deepEqual(result.series.map(({ keyword }) => keyword), TREND_KEYWORDS);
  assert.deepEqual(result.series[0].points, [
    { date: "2026-06-01", value: 18 },
    { date: "2026-06-08", value: 20 },
  ]);
  assert.deepEqual(result.series[1].points, [
    { date: "2026-06-01", value: 10 },
    { date: "2026-06-08", value: 15 },
  ]);
  assert.deepEqual(result.series[2].points, [
    { date: "2026-06-01", value: 35 },
    { date: "2026-06-08", value: 40 },
  ]);
});

test("ignores unrelated, malformed, and out-of-range records", () => {
  const result = buildTrendSeries([
    ...records,
    { date: "2026-06-09", keyword: "기타", value: 99 },
    { date: "not-a-date", keyword: "스피치", value: 50 },
    { date: "2026-02-31", keyword: "스피치", value: 50 },
    { date: "2026-06-10", keyword: "스피치", value: 101 },
  ]);

  assert.equal(result.dates.length, 2);
  assert.equal(result.series[2].points.length, 2);
});

test("renders an accessible SVG graph with a line for each keyword", () => {
  const container = new FakeElement("div");

  renderTrendChart(container, records, fakeDocument);

  const svg = container.children[0];
  assert.equal(svg.name, "svg");
  assert.equal(svg.attributes.role, "img");
  assert.equal(descendants(svg, "polyline").length, 3);
  assert.equal(descendants(svg, "circle").length, 6);
  assert.equal(container.children[1].children.length, 3);
});

test("shows an empty state when there are no valid weekly records", () => {
  const container = new FakeElement("div");

  renderTrendChart(container, [], fakeDocument);

  assert.equal(container.children.length, 1);
  assert.match(container.children[0].textContent, /데이터가 없습니다/);
});

test("JSON download serializes the actual records without dropping fields", () => {
  const exported = JSON.parse(serializeTrendDataJson(records));

  assert.deepEqual(exported, records);
});
