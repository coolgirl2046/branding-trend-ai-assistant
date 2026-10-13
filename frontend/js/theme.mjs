export const THEME_STORAGE_KEY = "branding-trend-theme";

function readTheme(storage) {
  try {
    return storage?.getItem(THEME_STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

function applyTheme(theme, root, button) {
  const isDark = theme === "dark";
  root.dataset.theme = theme;
  button.setAttribute("aria-pressed", String(isDark));
  button.setAttribute(
    "aria-label",
    `${isDark ? "라이트" : "다크"} 모드로 전환`,
  );
  button.textContent = `${isDark ? "라이트" : "다크"} 모드`;
}

export function setupThemeToggle(root, button, storage) {
  let theme = readTheme(storage);
  applyTheme(theme, root, button);

  button.addEventListener("click", () => {
    theme = theme === "dark" ? "light" : "dark";
    applyTheme(theme, root, button);
    try {
      storage?.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // The current page remains usable if browser storage is unavailable.
    }
  });
}
