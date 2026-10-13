import {
  createData,
  deleteConversation,
  deleteData,
  getConversation,
  getConversations,
  getData,
  getDataSummary,
  sendChatMessage,
  updateData,
} from "./api.js";
import {
  renderTrendChart,
  serializeTrendDataJson,
  TREND_KEYWORDS,
} from "./bonus_features.mjs";
import { setupThemeToggle } from "./theme.mjs";

const KEYWORDS = ["퍼스널브랜딩", "이미지메이킹", "스피치"];
const RELATIVE_INTEREST_NOTE =
  "네이버 데이터랩 값은 실제 검색량이 아닌 상대 검색 관심도 지수입니다.";
const summaryNumberFormatter = new Intl.NumberFormat("ko-KR", {
  maximumFractionDigits: 2,
});
const dataNumberFormatter = new Intl.NumberFormat("ko-KR", {
  maximumFractionDigits: 5,
});

const elements = {};
const conversationRecordsById = new Map();
const dataRecordsById = new Map();

let selectedConversationId = null;
let isChatSubmitting = false;
let isConversationDeleting = false;
let editingDataId = null;
let isDataSubmitting = false;
let isDataDeleting = false;
let trendRecords = [];
let trendPeriod = "6m";
let trendMode = "weekly";
let showTrendPoints = false;
const visibleTrendKeywords = new Set(TREND_KEYWORDS);

function getRequiredElement(id) {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Required element not found: #${id}`);
  }
  return element;
}

function cacheDomElements() {
  Object.assign(elements, {
    appLoading: getRequiredElement("app-loading"),
    appError: getRequiredElement("app-error"),
    appErrorMessage: getRequiredElement("app-error-message"),
    summaryRefreshButton: getRequiredElement("summary-refresh-button"),
    themeToggleButton: getRequiredElement("theme-toggle-button"),
    trendChart: getRequiredElement("trend-chart"),
    downloadDataButton: getRequiredElement("download-data-button"),
    downloadError: getRequiredElement("data-download-error"),
    trendPeriodSelect: getRequiredElement("trend-period-select"),
    trendModeSelect: getRequiredElement("trend-mode-select"),
    trendPointsCheckbox: getRequiredElement("trend-points-checkbox"),
    summaryStartDate: getRequiredElement("summary-start-date"),
    summaryEndDate: getRequiredElement("summary-end-date"),
    summaryTotalCount: getRequiredElement("summary-total-count"),
    keywordSummaryList: getRequiredElement("keyword-summary-list"),
    summaryRankingList: getRequiredElement("summary-ranking-list"),
    summaryMetricNote: getRequiredElement("summary-metric-note"),
    summaryEmpty: getRequiredElement("summary-empty"),
    conversationsLoading: getRequiredElement("conversations-loading"),
    conversationsError: getRequiredElement("conversations-error"),
    conversationsEmpty: getRequiredElement("conversations-empty"),
    conversationList: getRequiredElement("conversation-list"),
    newConversationButton: getRequiredElement("new-conversation-button"),
    activeConversationTitle: getRequiredElement("active-conversation-title"),
    chatMessages: getRequiredElement("chat-messages"),
    chatEmpty: getRequiredElement("chat-empty"),
    chatLoading: getRequiredElement("chat-loading"),
    chatError: getRequiredElement("chat-error"),
    chatForm: getRequiredElement("chat-form"),
    chatMessage: getRequiredElement("chat-message"),
    chatSubmitButton: getRequiredElement("chat-submit-button"),
    dataRefreshButton: getRequiredElement("data-refresh-button"),
    dataForm: getRequiredElement("data-form"),
    dataId: getRequiredElement("data-id"),
    dataDate: getRequiredElement("data-date"),
    dataKeyword: getRequiredElement("data-keyword"),
    dataValue: getRequiredElement("data-value"),
    dataMemo: getRequiredElement("data-memo"),
    dataSubmitButton: getRequiredElement("data-submit-button"),
    dataCancelEditButton: getRequiredElement("data-cancel-edit-button"),
    dataLoading: getRequiredElement("data-loading"),
    dataError: getRequiredElement("data-error"),
    dataTableBody: getRequiredElement("data-table-body"),
    dataEmpty: getRequiredElement("data-empty"),
  });
}

function setLoading(element, isLoading) {
  element.hidden = !isLoading;
}

function showError(element, message, messageElement = element) {
  messageElement.textContent = message;
  element.hidden = false;
}

function hideError(element, messageElement = element) {
  messageElement.textContent = "";
  element.hidden = true;
}

function setEmptyState(element, isEmpty) {
  element.hidden = !isEmpty;
}

function formatSummaryNumber(value) {
  return Number.isFinite(value)
    ? summaryNumberFormatter.format(value)
    : "데이터 부족";
}

function appendSummaryMetric(list, label, value) {
  const row = document.createElement("div");
  const term = document.createElement("dt");
  const description = document.createElement("dd");

  term.textContent = label;
  description.textContent = value;
  row.append(term, description);
  list.append(row);
}

function renderKeywordSummaries(keywordSummaries) {
  elements.keywordSummaryList.replaceChildren();

  for (const [index, keyword] of KEYWORDS.entries()) {
    const summary = keywordSummaries?.[keyword];
    if (!summary || typeof summary !== "object") {
      continue;
    }

    const article = document.createElement("article");
    const heading = document.createElement("h3");
    const metrics = document.createElement("dl");

    article.id = `keyword-summary-${index + 1}`;
    article.dataset.keyword = keyword;
    heading.textContent = keyword;
    appendSummaryMetric(
      metrics,
      "최근 4주 평균",
      formatSummaryNumber(summary.recent_4week_average),
    );
    appendSummaryMetric(
      metrics,
      "최근 추세",
      typeof summary.trend === "string" ? summary.trend : "데이터 부족",
    );

    article.append(heading, metrics);
    elements.keywordSummaryList.append(article);
  }
}

function renderSummaryRanking(ranking) {
  elements.summaryRankingList.replaceChildren();

  if (!Array.isArray(ranking)) {
    return;
  }

  for (const item of ranking) {
    if (!item || typeof item !== "object") {
      continue;
    }

    const listItem = document.createElement("li");
    const rank = Number.isInteger(item.rank) ? `${item.rank}위` : "순위 없음";
    const keyword =
      typeof item.keyword === "string" ? item.keyword : "키워드 없음";
    const average = formatSummaryNumber(item.recent_4week_average);
    listItem.textContent = `${rank} ${keyword}: ${average}`;
    elements.summaryRankingList.append(listItem);
  }
}

function resetSummaryView() {
  elements.summaryStartDate.textContent = "-";
  elements.summaryEndDate.textContent = "-";
  elements.summaryTotalCount.textContent = "-";
  elements.keywordSummaryList.replaceChildren();
  elements.summaryRankingList.replaceChildren();
  elements.summaryMetricNote.textContent = RELATIVE_INTEREST_NOTE;
}

function renderSummary(summary) {
  const hasData =
    summary && Number.isInteger(summary.total_count) && summary.total_count > 0;

  if (!hasData) {
    resetSummaryView();
    setEmptyState(elements.summaryEmpty, true);
    return;
  }

  setEmptyState(elements.summaryEmpty, false);
  elements.summaryStartDate.textContent = summary.start_date || "-";
  elements.summaryEndDate.textContent = summary.end_date || "-";
  elements.summaryTotalCount.textContent = summaryNumberFormatter.format(
    summary.total_count,
  );
  elements.summaryMetricNote.textContent =
    typeof summary.metric_note === "string" && summary.metric_note.trim()
      ? summary.metric_note
      : RELATIVE_INTEREST_NOTE;

  renderKeywordSummaries(summary.keywords);
  renderSummaryRanking(summary.ranking);
}

async function loadSummary() {
  setLoading(elements.appLoading, true);
  hideError(elements.appError);
  elements.summaryRefreshButton.disabled = true;

  try {
    const summary = await getDataSummary();
    renderSummary(summary);
  } catch (error) {
    resetSummaryView();
    setEmptyState(elements.summaryEmpty, false);
    showError(
      elements.appError,
      error instanceof Error
        ? error.message
        : "데이터 요약을 불러오지 못했습니다.",
      elements.appErrorMessage,
    );
  } finally {
    setLoading(elements.appLoading, false);
    elements.summaryRefreshButton.disabled = false;
  }
}

function createTableCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  return cell;
}

function createDataActionButton(label, action, documentId) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.dataset.action = action;
  button.dataset.documentId = documentId;
  return button;
}

function renderDataRows(records) {
  elements.dataTableBody.replaceChildren();
  dataRecordsById.clear();
  const fragment = document.createDocumentFragment();
  let renderedCount = 0;

  if (Array.isArray(records)) {
    for (const record of records) {
      if (!record || typeof record !== "object") {
        continue;
      }

      const row = document.createElement("tr");
      const date = typeof record.date === "string" ? record.date : "-";
      const keyword =
        typeof record.keyword === "string" ? record.keyword : "-";
      const value = Number.isFinite(record.value)
        ? dataNumberFormatter.format(record.value)
        : "-";
      const memo =
        typeof record.memo === "string" && record.memo.trim()
          ? record.memo
          : "-";
      const documentId =
        typeof record.id === "string" && record.id ? record.id : null;
      const actions = document.createElement("td");

      if (documentId) {
        dataRecordsById.set(documentId, {
          date: typeof record.date === "string" ? record.date : "",
          keyword: typeof record.keyword === "string" ? record.keyword : "",
          value: Number.isFinite(record.value) ? record.value : "",
          memo: typeof record.memo === "string" ? record.memo : "",
        });
      }

      row.append(
        createTableCell(date),
        createTableCell(keyword),
        createTableCell(value),
        createTableCell(memo),
      );

      if (documentId) {
        actions.append(
          createDataActionButton("수정", "edit", documentId),
          createDataActionButton("삭제", "delete", documentId),
        );
      } else {
        actions.textContent = "-";
      }

      row.append(actions);
      fragment.append(row);
      renderedCount += 1;
    }
  }

  elements.dataTableBody.append(fragment);
  setEmptyState(elements.dataEmpty, renderedCount === 0);
}

function renderCurrentTrendChart() {
  renderTrendChart(elements.trendChart, trendRecords, {
    period: trendPeriod,
    mode: trendMode,
    visibleKeywords: visibleTrendKeywords,
    showPoints: showTrendPoints,
  });
}

function handleTrendControlChange() {
  trendPeriod = elements.trendPeriodSelect.value;
  trendMode = elements.trendModeSelect.value;
  showTrendPoints = elements.trendPointsCheckbox.checked;
  renderCurrentTrendChart();
}

function handleTrendLegendClick(event) {
  const button = event.target.closest("button[data-keyword]");
  if (!button || !elements.trendChart.contains(button)) return;

  const keyword = button.dataset.keyword;
  if (visibleTrendKeywords.has(keyword)) {
    visibleTrendKeywords.delete(keyword);
  } else {
    visibleTrendKeywords.add(keyword);
  }
  renderCurrentTrendChart();
}

async function loadData() {
  setLoading(elements.dataLoading, true);
  hideError(elements.dataError);
  elements.dataRefreshButton.disabled = true;

  try {
    const records = await getData();
    trendRecords = records;
    renderDataRows(records);
    renderCurrentTrendChart();
  } catch (error) {
    trendRecords = [];
    elements.dataTableBody.replaceChildren();
    dataRecordsById.clear();
    elements.trendChart.replaceChildren();
    const chartError = document.createElement("p");
    chartError.textContent = "그래프 데이터를 불러오지 못했습니다.";
    elements.trendChart.append(chartError);
    setEmptyState(elements.dataEmpty, false);
    showError(
      elements.dataError,
      error instanceof Error
        ? error.message
        : "데이터 목록을 불러오지 못했습니다.",
    );
  } finally {
    setLoading(elements.dataLoading, false);
    elements.dataRefreshButton.disabled = false;
  }
}

async function handleDataDownload() {
  elements.downloadDataButton.disabled = true;
  hideError(elements.downloadError);
  try {
    const records = await getData();
    const blob = new Blob([serializeTrendDataJson(records)], {
      type: "application/json;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `branding-trend-data-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    showError(
      elements.downloadError,
      error instanceof Error ? error.message : "JSON 파일을 다운로드하지 못했습니다.",
    );
  } finally {
    elements.downloadDataButton.disabled = false;
  }
}

function setSelectedConversationId(conversationId) {
  selectedConversationId = conversationId;

  for (const button of elements.conversationList.querySelectorAll(
    'button[data-action="select"][data-conversation-id]',
  )) {
    const isSelected = button.dataset.conversationId === conversationId;
    button.classList.toggle("is-selected", isSelected);
    if (isSelected) {
      button.setAttribute("aria-current", "true");
    } else {
      button.removeAttribute("aria-current");
    }
  }
}

function renderConversationList(conversations) {
  elements.conversationList.replaceChildren();
  conversationRecordsById.clear();
  const fragment = document.createDocumentFragment();
  let renderedCount = 0;

  if (Array.isArray(conversations)) {
    for (const conversation of conversations) {
      if (
        !conversation ||
        typeof conversation !== "object" ||
        typeof conversation.id !== "string" ||
        !conversation.id
      ) {
        continue;
      }

      const item = document.createElement("li");
      const selectButton = document.createElement("button");
      const deleteButton = document.createElement("button");
      const title = document.createElement("span");
      const messageCount = document.createElement("span");
      const titleText =
        typeof conversation.title === "string" && conversation.title
          ? conversation.title
          : "제목 없는 대화";

      conversationRecordsById.set(conversation.id, { title: titleText });
      selectButton.type = "button";
      selectButton.dataset.action = "select";
      selectButton.dataset.conversationId = conversation.id;
      deleteButton.type = "button";
      deleteButton.dataset.action = "delete";
      deleteButton.dataset.conversationId = conversation.id;
      deleteButton.textContent = "삭제";
      deleteButton.setAttribute("aria-label", `${titleText} 대화 삭제`);
      title.textContent = titleText;
      messageCount.textContent = `메시지 ${Number.isInteger(conversation.message_count) ? conversation.message_count : 0}개`;
      selectButton.append(title, messageCount);
      item.append(selectButton, deleteButton);
      fragment.append(item);
      renderedCount += 1;
    }
  }

  elements.conversationList.append(fragment);
  setEmptyState(elements.conversationsEmpty, renderedCount === 0);
  setSelectedConversationId(selectedConversationId);
}

async function loadConversations() {
  setLoading(elements.conversationsLoading, true);
  hideError(elements.conversationsError);

  try {
    const conversations = await getConversations();
    renderConversationList(conversations);
  } catch (error) {
    elements.conversationList.replaceChildren();
    conversationRecordsById.clear();
    setEmptyState(elements.conversationsEmpty, false);
    showError(
      elements.conversationsError,
      error instanceof Error
        ? error.message
        : "대화 목록을 불러오지 못했습니다.",
    );
  } finally {
    setLoading(elements.conversationsLoading, false);
  }
}

function appendAssistantInlineContent(parent, text) {
  const boldPattern = /\*\*(.+?)\*\*/g;
  let cursor = 0;
  let match = boldPattern.exec(text);

  while (match) {
    if (match.index > cursor) {
      parent.append(document.createTextNode(text.slice(cursor, match.index)));
    }

    const bold = document.createElement("b");
    bold.textContent = match[1];
    parent.append(bold);
    cursor = boldPattern.lastIndex;
    match = boldPattern.exec(text);
  }

  if (cursor < text.length) {
    parent.append(document.createTextNode(text.slice(cursor)));
  }
}

function createAssistantTextBlock(tagName, lines) {
  const element = document.createElement(tagName);

  for (const [index, line] of lines.entries()) {
    if (index > 0) {
      element.append(document.createElement("br"));
    }
    appendAssistantInlineContent(element, line);
  }

  return element;
}

function renderAssistantContent(content) {
  const container = document.createElement("div");
  const lines = content.replace(/\r\n?/g, "\n").split("\n");
  let paragraphLines = [];
  let activeList = null;

  function flushParagraph() {
    if (paragraphLines.length > 0) {
      container.append(createAssistantTextBlock("p", paragraphLines));
      paragraphLines = [];
    }
  }

  for (const line of lines) {
    const headingMatch = line.match(/^\s*###\s+(.+)$/);
    const listItemMatch = line.match(/^\s*[*-]\s+(.+)$/);

    if (headingMatch) {
      flushParagraph();
      activeList = null;
      container.append(createAssistantTextBlock("h3", [headingMatch[1]]));
      continue;
    }

    if (listItemMatch) {
      flushParagraph();
      if (!activeList) {
        activeList = document.createElement("ul");
        container.append(activeList);
      }
      activeList.append(createAssistantTextBlock("li", [listItemMatch[1]]));
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      activeList = null;
      continue;
    }

    activeList = null;
    paragraphLines.push(line);
  }

  flushParagraph();
  return container;
}

function renderChatMessages(messages) {
  elements.chatMessages.replaceChildren();
  const fragment = document.createDocumentFragment();
  let renderedCount = 0;

  if (Array.isArray(messages)) {
    for (const message of messages) {
      if (
        !message ||
        typeof message !== "object" ||
        !["user", "assistant"].includes(message.role) ||
        typeof message.content !== "string"
      ) {
        continue;
      }

      const messageElement = document.createElement("article");
      const roleElement = document.createElement("strong");
      const contentElement =
        message.role === "assistant"
          ? renderAssistantContent(message.content)
          : document.createElement("p");

      messageElement.classList.add(
        "chat-message",
        `chat-message--${message.role}`,
      );
      messageElement.dataset.role = message.role;
      roleElement.textContent = message.role === "user" ? "사용자" : "AI";
      if (message.role === "user") {
        contentElement.textContent = message.content;
      }
      messageElement.append(roleElement, contentElement);
      fragment.append(messageElement);
      renderedCount += 1;
    }
  }

  elements.chatMessages.append(fragment);
  setEmptyState(elements.chatEmpty, renderedCount === 0);
}

async function loadConversation(conversationId) {
  setLoading(elements.chatLoading, true);
  elements.chatLoading.textContent = "대화를 불러오는 중입니다.";
  hideError(elements.chatError);

  try {
    const conversation = await getConversation(conversationId);
    if (
      !conversation ||
      typeof conversation !== "object" ||
      typeof conversation.id !== "string"
    ) {
      throw new Error("대화 응답 형식이 올바르지 않습니다.");
    }

    setSelectedConversationId(conversation.id);
    elements.activeConversationTitle.textContent =
      typeof conversation.title === "string" && conversation.title
        ? conversation.title
        : "제목 없는 대화";
    renderChatMessages(conversation.messages);
  } catch (error) {
    showError(
      elements.chatError,
      error instanceof Error
        ? error.message
        : "대화를 불러오지 못했습니다.",
    );
  } finally {
    setLoading(elements.chatLoading, false);
  }
}

function setEditingDataId(dataId) {
  editingDataId = dataId;
  elements.dataId.value = dataId ?? "";
}

function resetDataForm() {
  elements.dataForm.reset();
  setEditingDataId(null);
  elements.dataSubmitButton.textContent = "추가";
  elements.dataCancelEditButton.hidden = true;
}

function beginDataEdit(dataId) {
  const record = dataRecordsById.get(dataId);
  if (!record) {
    showError(elements.dataError, "수정할 데이터를 찾을 수 없습니다.");
    return;
  }

  hideError(elements.dataError);
  elements.dataDate.value = record.date;
  elements.dataKeyword.value = record.keyword;
  elements.dataValue.value = record.value;
  elements.dataMemo.value = record.memo;
  setEditingDataId(dataId);
  elements.dataSubmitButton.textContent = "수정 저장";
  elements.dataCancelEditButton.hidden = false;
  elements.dataDate.focus();
}

function handleSummaryRefresh() {
  void loadSummary();
}

function handleNewConversation() {
  setSelectedConversationId(null);
  elements.activeConversationTitle.textContent = "새 대화";
  elements.chatMessages.replaceChildren();
  setEmptyState(elements.chatEmpty, true);
  hideError(elements.chatError);
  elements.chatForm.reset();
}

async function handleConversationDelete(conversationId) {
  if (isConversationDeleting) {
    return;
  }

  const conversation = conversationRecordsById.get(conversationId);
  if (!conversation) {
    showError(elements.conversationsError, "삭제할 대화를 찾을 수 없습니다.");
    return;
  }

  const confirmed = window.confirm(
    `"${conversation.title}" 대화를 삭제하시겠습니까?`,
  );
  if (!confirmed) {
    return;
  }

  isConversationDeleting = true;
  setLoading(elements.conversationsLoading, true);
  hideError(elements.conversationsError);

  try {
    const response = await deleteConversation(conversationId);
    if (
      !response ||
      typeof response !== "object" ||
      response.deleted !== true ||
      response.id !== conversationId
    ) {
      throw new Error("대화 삭제 응답 형식이 올바르지 않습니다.");
    }

    if (selectedConversationId === conversationId) {
      handleNewConversation();
    }
    await loadConversations();
  } catch (error) {
    showError(
      elements.conversationsError,
      error instanceof Error
        ? error.message
        : "대화를 삭제하지 못했습니다.",
    );
  } finally {
    isConversationDeleting = false;
    setLoading(elements.conversationsLoading, false);
  }
}

function handleConversationListClick(event) {
  const button = event.target.closest(
    "button[data-action][data-conversation-id]",
  );
  if (!button || !elements.conversationList.contains(button)) {
    return;
  }

  if (button.dataset.action === "select") {
    void loadConversation(button.dataset.conversationId);
  } else if (button.dataset.action === "delete") {
    void handleConversationDelete(button.dataset.conversationId);
  }
}

async function handleChatSubmit(event) {
  event.preventDefault();

  if (isChatSubmitting) {
    return;
  }

  const message = elements.chatMessage.value.trim();
  if (!message) {
    showError(elements.chatError, "질문을 입력해주세요.");
    return;
  }

  isChatSubmitting = true;
  elements.chatSubmitButton.disabled = true;
  elements.chatLoading.textContent = "AI 답변을 생성하는 중입니다.";
  setLoading(elements.chatLoading, true);
  hideError(elements.chatError);

  try {
    const response = await sendChatMessage(message, selectedConversationId);
    if (
      !response ||
      typeof response !== "object" ||
      typeof response.conversation_id !== "string" ||
      !response.conversation_id ||
      typeof response.answer !== "string" ||
      !response.answer.trim()
    ) {
      throw new Error("채팅 응답 형식이 올바르지 않습니다.");
    }

    setSelectedConversationId(response.conversation_id);
    await Promise.all([
      loadConversation(response.conversation_id),
      loadConversations(),
    ]);
    elements.chatMessage.value = "";
  } catch (error) {
    showError(
      elements.chatError,
      error instanceof Error
        ? error.message
        : "AI 답변을 불러오지 못했습니다.",
    );
  } finally {
    isChatSubmitting = false;
    elements.chatSubmitButton.disabled = false;
    setLoading(elements.chatLoading, false);
  }
}

function handleDataRefresh() {
  void loadData();
}

async function handleDataSubmit(event) {
  event.preventDefault();

  if (isDataSubmitting) {
    return;
  }

  hideError(elements.dataError);

  const rawValue = elements.dataValue.value.trim();
  const value = Number(rawValue);
  if (!rawValue || !Number.isFinite(value)) {
    showError(elements.dataError, "상대 검색 관심도는 유한한 숫자여야 합니다.");
    return;
  }

  const payload = {
    date: elements.dataDate.value,
    keyword: elements.dataKeyword.value,
    value,
    memo: elements.dataMemo.value.trim() || null,
  };

  isDataSubmitting = true;
  elements.dataSubmitButton.disabled = true;
  const dataIdToUpdate = editingDataId;

  try {
    if (dataIdToUpdate) {
      await updateData(dataIdToUpdate, payload);
    } else {
      await createData(payload);
    }
    resetDataForm();
    await Promise.all([loadData(), loadSummary()]);
  } catch (error) {
    showError(
      elements.dataError,
      error instanceof Error
        ? error.message
        : dataIdToUpdate
          ? "데이터를 수정하지 못했습니다."
          : "데이터를 추가하지 못했습니다.",
    );
  } finally {
    isDataSubmitting = false;
    elements.dataSubmitButton.disabled = false;
  }
}

function handleDataCancelEdit() {
  resetDataForm();
  hideError(elements.dataError);
}

async function handleDataDelete(dataId) {
  if (isDataDeleting) {
    return;
  }

  const record = dataRecordsById.get(dataId);
  if (!record) {
    showError(elements.dataError, "삭제할 데이터를 찾을 수 없습니다.");
    return;
  }

  const confirmed = window.confirm(
    `${record.date} ${record.keyword} 데이터를 삭제하시겠습니까?`,
  );
  if (!confirmed) {
    return;
  }

  isDataDeleting = true;
  setLoading(elements.dataLoading, true);
  hideError(elements.dataError);
  elements.dataRefreshButton.disabled = true;

  try {
    await deleteData(dataId);
    if (editingDataId === dataId) {
      resetDataForm();
    }
    await Promise.all([loadData(), loadSummary()]);
  } catch (error) {
    showError(
      elements.dataError,
      error instanceof Error
        ? error.message
        : "데이터를 삭제하지 못했습니다.",
    );
  } finally {
    isDataDeleting = false;
    setLoading(elements.dataLoading, false);
    elements.dataRefreshButton.disabled = false;
  }
}

function handleDataTableClick(event) {
  const button = event.target.closest("button[data-action][data-document-id]");
  if (!button || !elements.dataTableBody.contains(button)) {
    return;
  }

  if (button.dataset.action === "edit") {
    beginDataEdit(button.dataset.documentId);
  } else if (button.dataset.action === "delete") {
    void handleDataDelete(button.dataset.documentId);
  }
}

function bindEventListeners() {
  elements.summaryRefreshButton.addEventListener("click", handleSummaryRefresh);
  elements.downloadDataButton.addEventListener("click", handleDataDownload);
  elements.trendPeriodSelect.addEventListener("change", handleTrendControlChange);
  elements.trendModeSelect.addEventListener("change", handleTrendControlChange);
  elements.trendPointsCheckbox.addEventListener("change", handleTrendControlChange);
  elements.trendChart.addEventListener("click", handleTrendLegendClick);
  let themeStorage = null;
  try {
    themeStorage = window.localStorage;
  } catch {
    // Theme switching still works for this page when storage is blocked.
  }
  setupThemeToggle(
    document.documentElement,
    elements.themeToggleButton,
    themeStorage,
  );
  elements.newConversationButton.addEventListener("click", handleNewConversation);
  elements.conversationList.addEventListener(
    "click",
    handleConversationListClick,
  );
  elements.chatForm.addEventListener("submit", handleChatSubmit);
  elements.dataRefreshButton.addEventListener("click", handleDataRefresh);
  elements.dataForm.addEventListener("submit", handleDataSubmit);
  elements.dataCancelEditButton.addEventListener(
    "click",
    handleDataCancelEdit,
  );
  elements.dataTableBody.addEventListener("click", handleDataTableClick);
}

function initializeViewState() {
  setLoading(elements.appLoading, false);
  setLoading(elements.conversationsLoading, false);
  setLoading(elements.chatLoading, false);
  setLoading(elements.dataLoading, false);

  hideError(elements.appError, elements.appErrorMessage);
  hideError(elements.conversationsError);
  hideError(elements.chatError);
  hideError(elements.dataError);

  setEmptyState(elements.summaryEmpty, true);
  setEmptyState(elements.conversationsEmpty, true);
  setEmptyState(elements.chatEmpty, true);
  setEmptyState(elements.dataEmpty, true);
}

function initializeApp() {
  cacheDomElements();
  initializeViewState();
  bindEventListeners();
  void loadSummary();
  void loadData();
  void loadConversations();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeApp, { once: true });
} else {
  initializeApp();
}
