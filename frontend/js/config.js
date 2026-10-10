const isLocalDevelopment = ["localhost", "127.0.0.1", ""].includes(
  window.location.hostname,
);

// Use the deployed Render service outside local development.
const deployedApiBaseUrl = "https://branding-trend-ai-assistant.onrender.com";

export const API_CONFIG = Object.freeze({
  baseUrl: isLocalDevelopment ? "http://127.0.0.1:8000" : deployedApiBaseUrl,
});
