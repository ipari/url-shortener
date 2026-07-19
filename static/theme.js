(() => {
  const storageKey = 'theme';
  const root = document.documentElement;
  const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
  const allowedThemes = new Set(['light', 'dark']);

  let preference = 'system';
  try {
    const savedTheme = localStorage.getItem(storageKey);
    if (allowedThemes.has(savedTheme)) preference = savedTheme;
  } catch {
    // localStorage가 차단돼도 현재 탭에서는 테마 전환을 지원한다.
  }

  const applyTheme = () => {
    const resolved = preference === 'system'
      ? (systemTheme.matches ? 'dark' : 'light')
      : preference;
    root.dataset.theme = resolved;
    root.dataset.themePreference = preference;
  };

  const savePreference = () => {
    try {
      if (preference === 'system') localStorage.removeItem(storageKey);
      else localStorage.setItem(storageKey, preference);
    } catch {
      // 저장할 수 없는 환경에서는 현재 페이지에만 적용한다.
    }
  };

  applyTheme();

  document.addEventListener('DOMContentLoaded', () => {
    const selectors = document.querySelectorAll('[data-theme-selector]');
    selectors.forEach((selector) => {
      selector.value = preference;
      selector.addEventListener('change', () => {
        preference = selector.value;
        savePreference();
        applyTheme();
        selectors.forEach((item) => { item.value = preference; });
      });
    });
  });

  systemTheme.addEventListener('change', () => {
    if (preference === 'system') applyTheme();
  });
})();
