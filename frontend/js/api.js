import { API_CONFIG } from "./config.js";

const API_BASE_URL = API_CONFIG.baseUrl.replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(message, status = 0, details = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

async function readResponse(response) {
  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text ? { detail: text } : null;
}

export async function apiRequest(path, options = {}) {
  if (!API_BASE_URL) {
    throw new ApiError("API 서버 주소가 설정되지 않았습니다. 배포 환경의 API_BASE_URL을 확인해 주세요.");
  }
  const headers = new Headers(options.headers || {});
  const hasBody = options.body !== undefined;

  if (hasBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      body: hasBody ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError("서버에 연결할 수 없습니다.");
  }

  let payload;
  try {
    payload = await readResponse(response);
  } catch {
    throw new ApiError("서버 응답을 처리할 수 없습니다.", response.status);
  }

  if (!response.ok) {
    const message =
      payload && typeof payload.detail === "string"
        ? payload.detail
        : `요청에 실패했습니다. (HTTP ${response.status})`;
    throw new ApiError(message, response.status, payload);
  }

  return payload;
}

export function getData() {
  return apiRequest("/api/data");
}

export function getDataSummary() {
  return apiRequest("/api/data/summary");
}

export function createData(data) {
  return apiRequest("/api/data", {
    method: "POST",
    body: data,
  });
}

export function updateData(id, data) {
  return apiRequest(`/api/data/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: data,
  });
}

export function deleteData(id) {
  return apiRequest(`/api/data/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export function createConversation(conversation) {
  return apiRequest("/api/conversations", {
    method: "POST",
    body: conversation,
  });
}

export function getConversations() {
  return apiRequest("/api/conversations");
}

export function getConversation(id) {
  return apiRequest(`/api/conversations/${encodeURIComponent(id)}`);
}

export function deleteConversation(id) {
  return apiRequest(`/api/conversations/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export function sendChatMessage(message, conversationId = null) {
  const body = { message };
  if (conversationId) {
    body.conversation_id = conversationId;
  }

  return apiRequest("/api/chat", {
    method: "POST",
    body,
  });
}
