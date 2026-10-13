export const TREND_KEYWORDS = ["퍼스널브랜딩", "이미지메이킹", "스피치"];

const SVG_NS = "http://www.w3.org/2000/svg";
const CHART = { width: 960, height: 360, left: 64, right: 936, top: 24, bottom: 294 };

function isIsoDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

export function buildTrendSeries(records) {
  const normalized = (Array.isArray(records) ? records : [])
    .filter(
      (record) =>
        record &&
        TREND_KEYWORDS.includes(record.keyword) &&
        isIsoDate(record.date) &&
        Number.isFinite(record.value) &&
        record.value >= 0 &&
        record.value <= 100,
    )
    .map(({ date, keyword, value }) => ({ date, keyword, value }))
    .sort((left, right) => left.date.localeCompare(right.date));

  const dates = [...new Set(normalized.map((record) => record.date))];
  const series = TREND_KEYWORDS.map((keyword) => ({
    keyword,
    points: normalized
      .filter((record) => record.keyword === keyword)
      .map(({ date, value }) => ({ date, value })),
  }));

  return { dates, series };
}

function createSvgElement(documentRef, name, attributes = {}) {
  const element = documentRef.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, String(value));
  }
  return element;
}

function datePosition(date) {
  return Date.parse(`${date}T00:00:00Z`);
}

export function renderTrendChart(container, records, documentRef = document) {
  const { dates, series } = buildTrendSeries(records);
  container.replaceChildren();

  if (dates.length === 0) {
    const empty = documentRef.createElement("p");
    empty.textContent = "그래프에 표시할 검색 관심도 데이터가 없습니다.";
    container.append(empty);
    return;
  }

  const svg = createSvgElement(documentRef, "svg", {
    class: "trend-chart-svg",
    viewBox: `0 0 ${CHART.width} ${CHART.height}`,
    role: "img",
    "aria-labelledby": "trend-chart-svg-title trend-chart-svg-description",
    preserveAspectRatio: "xMidYMid meet",
  });
  const title = createSvgElement(documentRef, "title", { id: "trend-chart-svg-title" });
  title.textContent = "세 키워드의 주간 상대 검색 관심도 추이";
  const description = createSvgElement(documentRef, "desc", {
    id: "trend-chart-svg-description",
  });
  description.textContent = "세 키워드의 날짜별 관심도 지수를 0부터 100까지 선 그래프로 비교합니다.";
  svg.append(title, description);

  const times = dates.map(datePosition);
  const minTime = times[0];
  const maxTime = times[times.length - 1];
  const timeRange = maxTime - minTime || 1;
  const x = (date) =>
    CHART.left + ((datePosition(date) - minTime) / timeRange) * (CHART.right - CHART.left);
  const y = (value) => CHART.bottom - (value / 100) * (CHART.bottom - CHART.top);

  for (let value = 0; value <= 100; value += 20) {
    const yPosition = y(value);
    svg.append(
      createSvgElement(documentRef, "line", {
        class: "trend-chart-gridline",
        x1: CHART.left,
        x2: CHART.right,
        y1: yPosition,
        y2: yPosition,
      }),
    );
    const label = createSvgElement(documentRef, "text", {
      class: "trend-chart-axis-label",
      x: CHART.left - 12,
      y: yPosition + 4,
      "text-anchor": "end",
    });
    label.textContent = String(value);
    svg.append(label);
  }

  const tickCount = Math.min(6, dates.length);
  const tickIndexes = [...new Set(
    Array.from({ length: tickCount }, (_, index) =>
      Math.round((index * (dates.length - 1)) / Math.max(tickCount - 1, 1)),
    ),
  )];
  for (const index of tickIndexes) {
    const tickDate = dates[index];
    const xPosition = x(tickDate);
    svg.append(
      createSvgElement(documentRef, "line", {
        class: "trend-chart-gridline trend-chart-gridline--vertical",
        x1: xPosition,
        x2: xPosition,
        y1: CHART.top,
        y2: CHART.bottom,
      }),
    );
    const label = createSvgElement(documentRef, "text", {
      class: "trend-chart-axis-label",
      x: xPosition,
      y: CHART.bottom + 24,
      "text-anchor":
        index === 0 ? "start" : index === tickIndexes[tickIndexes.length - 1] ? "end" : "middle",
    });
    label.textContent = tickDate;
    svg.append(label);
  }

  series.forEach(({ keyword, points }, index) => {
    if (points.length === 0) return;
    const seriesClass = `trend-series-${index + 1}`;
    const coordinates = points.map((point) => `${x(point.date)},${y(point.value)}`);
    svg.append(
      createSvgElement(documentRef, "polyline", {
        class: `trend-chart-line ${seriesClass}`,
        points: coordinates.join(" "),
      }),
    );

    for (const point of points) {
      const circle = createSvgElement(documentRef, "circle", {
        class: `trend-chart-point ${seriesClass}`,
        cx: x(point.date),
        cy: y(point.value),
        r: 4,
      });
      const pointTitle = createSvgElement(documentRef, "title");
      pointTitle.textContent = `${point.date} · ${keyword}: ${point.value}`;
      circle.append(pointTitle);
      svg.append(circle);
    }
  });

  container.append(svg);
  const legend = documentRef.createElement("ul");
  legend.className = "trend-chart-legend";
  series.forEach(({ keyword }, index) => {
    const item = documentRef.createElement("li");
    const swatch = documentRef.createElement("span");
    swatch.className = `trend-chart-swatch trend-series-${index + 1}`;
    swatch.setAttribute("aria-hidden", "true");
    const label = documentRef.createElement("span");
    label.textContent = keyword;
    item.append(swatch, label);
    legend.append(item);
  });
  container.append(legend);
}

export function serializeTrendDataJson(records) {
  return `${JSON.stringify(Array.isArray(records) ? records : [], null, 2)}\n`;
}
