const fs = require("node:fs");
const path = require("node:path");
function createConfig(value) {
  if (!value) throw new Error("Vercel 환경변수 API_BASE_URL을 설정해 주세요.");
  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error("API_BASE_URL은 인증정보 없는 HTTP(S) 주소여야 합니다.");
  }
  return `globalThis.__APP_CONFIG__ = Object.freeze(${JSON.stringify({API_BASE_URL: url.href.replace(/\/$/, "")})});\n`;
}
if (require.main === module) {
  fs.writeFileSync(path.join(__dirname, "../js/runtime-config.js"), createConfig(process.env.API_BASE_URL));
}
module.exports = { createConfig };
