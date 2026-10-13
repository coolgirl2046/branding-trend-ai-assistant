import assert from "node:assert/strict";
import test from "node:test";

import {
  buildTrendSeries,
  calculateFourWeekAverage,
  renderTrendChart,
  serializeTrendDataJson,
  subtractCalendarMonths,
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
    this.dataset = {};
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

test("defaults to six months and supports three months, one year, and all history", () => {
  const start = Date.parse("2025-01-06T00:00:00Z");
  const weeklyRecords = Array.from({ length: 35 }, (_, index) => ({
    date: new Date(start + index * 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
    keyword: "퍼스널브랜딩",
    value: index,
  }));
  const latest = weeklyRecords.at(-1).date;

  assert.equal(buildTrendSeries(weeklyRecords).startDate, subtractCalendarMonths(latest, 6));
  assert.equal(buildTrendSeries(weeklyRecords, { period: "3m" }).startDate, subtractCalendarMonths(latest, 3));
  assert.equal(buildTrendSeries(weeklyRecords, { period: "1y" }).startDate, subtractCalendarMonths(latest, 12));
  assert.equal(buildTrendSeries(weeklyRecords, { period: "all" }).startDate, null);
  assert.equal(subtractCalendarMonths("2024-03-31", 1), "2024-02-29");
});

test("calculates exact rolling averages and skips windows with a missing week", () => {
  const consecutive = [
    { date: "2025-01-06", value: 10 },
    { date: "2025-01-13", value: 20 },
    { date: "2025-01-20", value: 30 },
    { date: "2025-01-27", value: 40 },
    { date: "2025-02-03", value: 50 },
  ];
  assert.deepEqual(calculateFourWeekAverage(consecutive), [
    { date: "2025-01-27", value: 25 },
    { date: "2025-02-03", value: 35 },
  ]);

  const points = [
    { date: "2025-01-06", value: 10 },
    { date: "2025-01-13", value: 20 },
    { date: "2025-01-20", value: 30 },
    { date: "2025-01-27", value: 40 },
    { date: "2025-02-10", value: 60 },
  ];

  assert.deepEqual(calculateFourWeekAverage(points), [
    { date: "2025-01-27", value: 25 },
  ]);
});

test("computes moving averages before applying the visible period boundary", () => {
  const start = Date.parse("2025-01-06T00:00:00Z");
  const weeklyRecords = Array.from({ length: 35 }, (_, index) => ({
    date: new Date(start + index * 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
    keyword: "퍼스널브랜딩",
    value: index,
  }));
  const raw = buildTrendSeries(weeklyRecords, { period: "6m", mode: "weekly" });
  const averaged = buildTrendSeries(weeklyRecords, { period: "6m", mode: "average" });
  const firstVisibleRawIndex = weeklyRecords.findIndex((record) => record.date >= raw.startDate);

  assert.equal(averaged.series[0].points[0].date, weeklyRecords[firstVisibleRawIndex].date);
  assert.equal(averaged.series[0].points[0].value, firstVisibleRawIndex - 1.5);
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

  renderTrendChart(container, records, {}, fakeDocument);

  const svg = container.children[0];
  assert.equal(svg.name, "svg");
  assert.equal(svg.attributes.role, "img");
  assert.equal(descendants(svg, "polyline").length, 3);
  assert.equal(descendants(svg, "circle").length, 0);
  assert.deepEqual(
    descendants(svg, "polyline").map((line) => line.attributes.class),
    ["trend-chart-line trend-series-1", "trend-chart-line trend-series-2", "trend-chart-line trend-series-3"],
  );
  assert.deepEqual(
    container.children[1].children.map((button) => button.children[0].className),
    ["trend-chart-swatch trend-series-1", "trend-chart-swatch trend-series-2", "trend-chart-swatch trend-series-3"],
  );
  assert.equal(container.children[1].children.length, 3);
});

test("hides data points by default and can hide individual keyword lines", () => {
  const container = new FakeElement("div");

  renderTrendChart(container, records, { visibleKeywords: ["스피치"] }, fakeDocument);

  assert.equal(descendants(container.children[0], "polyline").length, 1);
  assert.equal(descendants(container.children[0], "circle").length, 0);
  assert.equal(container.children[1].children[0].attributes["aria-pressed"], "false");
  assert.equal(container.children[1].children[2].attributes["aria-pressed"], "true");
});

test("shows data points only when explicitly requested", () => {
  const container = new FakeElement("div");

  renderTrendChart(container, records, { showPoints: true }, fakeDocument);

  assert.equal(descendants(container.children[0], "circle").length, 6);
});

test("shows an empty state when there are no valid weekly records", () => {
  const container = new FakeElement("div");

  renderTrendChart(container, [], {}, fakeDocument);

  assert.equal(container.children.length, 2);
  assert.match(container.children[0].textContent, /데이터가 없습니다/);
});

test("explains when the selected period has too little history for moving averages", () => {
  const container = new FakeElement("div");

  renderTrendChart(container, records.slice(0, 3), { mode: "average" }, fakeDocument);

  assert.match(container.children[0].textContent, /연속된 주간 데이터 4개/);
});

test("JSON download serializes the actual records without dropping fields", () => {
  const exported = JSON.parse(serializeTrendDataJson(records));

  assert.deepEqual(exported, records);
});
