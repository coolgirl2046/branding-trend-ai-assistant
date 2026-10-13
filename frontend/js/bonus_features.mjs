export const TREND_KEYWORDS = ["퍼스널브랜딩", "이미지메이킹", "스피치"];
export const TREND_PERIOD_MONTHS = Object.freeze({ "3m": 3, "6m": 6, "1y": 12 });

const SVG_NS = "http://www.w3.org/2000/svg";
const WEEK_MS = 7 * 24 * 60 * 60 * 1000;
const CHART = { width: 960, height: 360, left: 64, right: 936, top: 24, bottom: 294 };

function isIsoDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function datePosition(date) {
  return Date.parse(`${date}T00:00:00Z`);
}

export function subtractCalendarMonths(date, months) {
  const [year, month, day] = date.split("-").map(Number);
  const monthIndex = year * 12 + month - 1 - months;
  const targetYear = Math.floor(monthIndex / 12);
  const targetMonth = ((monthIndex % 12) + 12) % 12;
  const lastDay = new Date(Date.UTC(targetYear, targetMonth + 1, 0)).getUTCDate();
  return `${String(targetYear).padStart(4, "0")}-${String(targetMonth + 1).padStart(2, "0")}-${String(Math.min(day, lastDay)).padStart(2, "0")}`;
}

export function calculateFourWeekAverage(points) {
  const sorted = [...points].sort((left, right) => left.date.localeCompare(right.date));
  const averages = [];
  for (let index = 3; index < sorted.length; index += 1) {
    const window = sorted.slice(index - 3, index + 1);
    const isFourConsecutiveWeeks = window.every(
      (point, offset) => offset === 0 || datePosition(point.date) - datePosition(window[offset - 1].date) === WEEK_MS,
    );
    if (!isFourConsecutiveWeeks) continue;
    const value = window.reduce((sum, point) => sum + point.value, 0) / 4;
    averages.push({ date: sorted[index].date, value });
  }
  return averages;
}

export function buildTrendSeries(records, { period = "6m", mode = "weekly" } = {}) {
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

  const latestDate = normalized.at(-1)?.date ?? null;
  const monthCount = TREND_PERIOD_MONTHS[period];
  const startDate = latestDate && monthCount ? subtractCalendarMonths(latestDate, monthCount) : null;
  const series = TREND_KEYWORDS.map((keyword) => {
    const weeklyPoints = normalized
      .filter((record) => record.keyword === keyword)
      .map(({ date, value }) => ({ date, value }));
    // Calculate with full history before clipping to the selected period so
    // its first visible average can use the preceding three real weeks.
    const allPoints = mode === "average" ? calculateFourWeekAverage(weeklyPoints) : weeklyPoints;
    return {
      keyword,
      points: allPoints.filter((point) => !startDate || point.date >= startDate),
    };
  });
  const dates = [...new Set(series.flatMap(({ points }) => points.map(({ date }) => date)))].sort();

  return { dates, latestDate, startDate, series };
}

function createSvgElement(documentRef, name, attributes = {}) {
  const element = documentRef.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, String(value));
  }
  return element;
}

function selectTickIndexes(dates, maxTicks = 6) {
  if (dates.length <= maxTicks) return dates.map((_, index) => index);
  const first = datePosition(dates[0]);
  const last = datePosition(dates.at(-1));
  const selected = new Set();
  for (let tick = 0; tick < maxTicks; tick += 1) {
    const target = first + ((last - first) * tick) / (maxTicks - 1);
    let closestIndex = 0;
    for (let index = 1; index < dates.length; index += 1) {
      if (Math.abs(datePosition(dates[index]) - target) < Math.abs(datePosition(dates[closestIndex]) - target)) {
        closestIndex = index;
      }
    }
    selected.add(closestIndex);
  }
  return [...selected].sort((left, right) => left - right);
}

function formatAxisDate(date, totalDays) {
  return totalDays > 400
    ? date.slice(2, 7).replace("-", ".")
    : date.slice(5).replace("-", ".");
}

export function renderTrendChart(
  container,
  records,
  {
    period = "6m",
    mode = "weekly",
    visibleKeywords = TREND_KEYWORDS,
    showPoints = false,
  } = {},
  documentRef = document,
) {
  const { dates, latestDate, startDate, series } = buildTrendSeries(records, { period, mode });
  const visible = new Set(visibleKeywords);
  const activeSeries = series.filter(
    ({ keyword, points }) => visible.has(keyword) && points.length > 0,
  );
  container.replaceChildren();

  if (dates.length === 0) {
    const empty = documentRef.createElement("p");
    empty.textContent = mode === "average"
      ? "4주 이동평균에는 연속된 주간 데이터 4개 이상이 필요합니다."
      : "선택한 기간에 표시할 검색 관심도 데이터가 없습니다.";
    container.append(empty);
  } else {
    const svg = createSvgElement(documentRef, "svg", {
      class: "trend-chart-svg",
      viewBox: `0 0 ${CHART.width} ${CHART.height}`,
      role: "img",
      "aria-labelledby": "trend-chart-svg-title trend-chart-svg-description",
      preserveAspectRatio: "xMidYMid meet",
    });
    const title = createSvgElement(documentRef, "title", { id: "trend-chart-svg-title" });
    title.textContent = mode === "average"
      ? "세 키워드의 4주 이동평균 상대 검색 관심도 추이"
      : "세 키워드의 주간 상대 검색 관심도 추이";
    const description = createSvgElement(documentRef, "desc", {
      id: "trend-chart-svg-description",
    });
    description.textContent = `날짜 범위 ${startDate ?? dates[0]}부터 ${latestDate}까지. 지수 범위는 0부터 100입니다.`;
    svg.append(title, description);

    const firstTime = datePosition(dates[0]);
    const lastTime = datePosition(dates.at(-1));
    const timeRange = lastTime - firstTime || 1;
    const totalDays = timeRange / WEEK_MS * 7;
    const x = (date) => CHART.left + ((datePosition(date) - firstTime) / timeRange) * (CHART.right - CHART.left);
    const y = (value) => CHART.bottom - (value / 100) * (CHART.bottom - CHART.top);

    for (let value = 0; value <= 100; value += 20) {
      const yPosition = y(value);
      svg.append(createSvgElement(documentRef, "line", {
        class: "trend-chart-gridline",
        x1: CHART.left,
        x2: CHART.right,
        y1: yPosition,
        y2: yPosition,
      }));
      const label = createSvgElement(documentRef, "text", {
        class: "trend-chart-axis-label",
        x: CHART.left - 12,
        y: yPosition + 4,
        "text-anchor": "end",
      });
      label.textContent = String(value);
      svg.append(label);
    }

    const tickIndexes = selectTickIndexes(dates);
    for (const [tickPosition, index] of tickIndexes.entries()) {
      const tickDate = dates[index];
      const xPosition = x(tickDate);
      svg.append(createSvgElement(documentRef, "line", {
        class: "trend-chart-gridline trend-chart-gridline--vertical",
        x1: xPosition,
        x2: xPosition,
        y1: CHART.top,
        y2: CHART.bottom,
      }));
      const label = createSvgElement(documentRef, "text", {
        class: "trend-chart-axis-label",
        x: xPosition,
        y: CHART.bottom + 24,
        "text-anchor": tickPosition === 0
          ? "start"
          : tickPosition === tickIndexes.length - 1 ? "end" : "middle",
      });
      label.textContent = formatAxisDate(tickDate, totalDays);
      svg.append(label);
    }

    activeSeries.forEach(({ keyword, points }) => {
      const index = TREND_KEYWORDS.indexOf(keyword);
      if (points.length === 0) return;
      const seriesClass = `trend-series-${index + 1}`;
      const coordinates = points.map((point) => `${x(point.date)},${y(point.value)}`);
      svg.append(createSvgElement(documentRef, "polyline", {
        class: `trend-chart-line ${seriesClass}`,
        points: coordinates.join(" "),
      }));

      if (showPoints) {
        for (const point of points) {
          const circle = createSvgElement(documentRef, "circle", {
            class: `trend-chart-point ${seriesClass}`,
            cx: x(point.date),
            cy: y(point.value),
            r: 3,
          });
          const pointTitle = createSvgElement(documentRef, "title");
          pointTitle.textContent = `${point.date} · ${keyword}: ${point.value}`;
          circle.append(pointTitle);
          svg.append(circle);
        }
      }
    });

    if (activeSeries.length === 0) {
      const message = createSvgElement(documentRef, "text", {
        class: "trend-chart-empty-selection",
        x: (CHART.left + CHART.right) / 2,
        y: (CHART.top + CHART.bottom) / 2,
        "text-anchor": "middle",
      });
      message.textContent = visible.size === 0
        ? "범례에서 표시할 키워드를 선택하세요."
        : "선택한 기간에 표시할 키워드 데이터가 없습니다.";
      svg.append(message);
    }
    container.append(svg);
  }

  const legend = documentRef.createElement("div");
  legend.className = "trend-chart-legend";
  series.forEach(({ keyword }) => {
    const index = TREND_KEYWORDS.indexOf(keyword);
    const isVisible = visible.has(keyword);
    const button = documentRef.createElement("button");
    button.type = "button";
    button.className = "trend-legend-toggle";
    button.dataset.keyword = keyword;
    button.setAttribute("aria-pressed", String(isVisible));
    const swatch = documentRef.createElement("span");
    swatch.className = `trend-chart-swatch trend-series-${index + 1}`;
    swatch.setAttribute("aria-hidden", "true");
    const label = documentRef.createElement("span");
    label.textContent = keyword;
    button.append(swatch, label);
    legend.append(button);
  });
  container.append(legend);
}

export function serializeTrendDataJson(records) {
  return `${JSON.stringify(Array.isArray(records) ? records : [], null, 2)}\n`;
}
