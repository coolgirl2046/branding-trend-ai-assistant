const isLocalDevelopment = ["localhost", "127.0.0.1", ""].includes(
  window.location.hostname,
);

// Set this to the Render service URL after creating the backend service.
// Keep it empty until the real URL is available; local development remains
// pointed at the local FastAPI server.
const deployedApiBaseUrl = "";

export const API_CONFIG = Object.freeze({
  baseUrl: isLocalDevelopment ? "http://127.0.0.1:8000" : deployedApiBaseUrl,
});
