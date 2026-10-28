(() => {
    const controls = document.querySelectorAll('[data-theme-toggle]');
    const sync = () => {
        const dark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        controls.forEach(button => {
            button.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
            button.setAttribute('aria-pressed', String(dark));
            const icon = button.querySelector('i');
            if (icon) icon.className = dark ? 'bi bi-sun' : 'bi bi-moon';
        });
    };
    controls.forEach(button => button.addEventListener('click', () => {
        const theme = document.documentElement.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-bs-theme', theme);
        try { localStorage.setItem('maisha-theme', theme); } catch (_) {}
        sync();
    }));
    window.addEventListener('storage', event => {
        if (event.key === 'maisha-theme') {
            document.documentElement.setAttribute('data-bs-theme', event.newValue === 'dark' ? 'dark' : 'light');
            sync();
        }
    });
    sync();
})();
