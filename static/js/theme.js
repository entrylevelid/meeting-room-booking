(() => {
    'use strict';
    const storageKey = 'ruang-theme';
    const root = document.documentElement;

    function applyTheme(theme) {
        const dark = theme === 'dark';
        root.dataset.theme = dark ? 'dark' : 'light';
        root.style.colorScheme = dark ? 'dark' : 'light';
        document.querySelector('meta[name="theme-color"]').content = dark ? '#141414' : '#fff8e7';
        document.querySelectorAll('[data-theme-toggle]').forEach(button => {
            button.setAttribute('aria-checked', String(dark));
            button.title = dark ? 'Aktifkan tema terang' : 'Aktifkan tema gelap';
        });
    }

    let initialTheme = 'light';
    try {
        initialTheme = localStorage.getItem(storageKey) || 'light';
    } catch {
        // localStorage can be blocked; start with the light theme.
    }
    applyTheme(initialTheme);
    document.addEventListener('DOMContentLoaded', () => applyTheme(root.dataset.theme));
    document.addEventListener('click', event => {
        if (!event.target.closest('[data-theme-toggle]')) return;
        const theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
        applyTheme(theme);
        try {
            localStorage.setItem(storageKey, theme);
        } catch {
            // Not saved; the theme still applies to this page.
        }
    });
    window.addEventListener('storage', event => {
        if (event.key === storageKey || event.key === null) applyTheme(event.newValue);
    });
})();
