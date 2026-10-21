const isLocalDevelopment = ["localhost", "127.0.0.1", ""].includes(window.location.hostname);
const configuredApiBaseUrl = globalThis.__APP_CONFIG__?.API_BASE_URL;
export const API_CONFIG = Object.freeze({
  baseUrl: configuredApiBaseUrl || (isLocalDevelopment ? "http://127.0.0.1:8000" : ""),
});
