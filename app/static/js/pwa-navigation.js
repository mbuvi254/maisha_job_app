(() => {
    const toolbar = document.querySelector('.pwa-navigation');
    const displayModes = ['standalone','fullscreen','window-controls-overlay'].map(mode=>window.matchMedia(`(display-mode: ${mode})`));
    function update() {
        const standalone = window.navigator.standalone === true || displayModes.some(mode=>mode.matches);
        document.documentElement.classList.toggle('pwa-running',standalone);
        if (toolbar) {
            toolbar.hidden=!standalone;
            const navigation=window.navigation;
            toolbar.querySelector('[data-app-back]').disabled=navigation ? !navigation.canGoBack : window.history.length<=1;
            // Older browsers do not expose the forward stack; forward() is a safe no-op at its end.
            toolbar.querySelector('[data-app-forward]').disabled=navigation ? !navigation.canGoForward : false;
        }
    }
    document.querySelectorAll('[data-app-back],[data-page-back]').forEach(button=>button.addEventListener('click',()=>{
        if (window.navigation ? window.navigation.canGoBack : window.history.length>1) window.history.back();
        else window.location.assign('/');
    }));
    document.querySelector('[data-app-forward]')?.addEventListener('click',()=>window.history.forward());
    document.querySelector('[data-app-refresh]')?.addEventListener('click',()=>window.location.reload());
    displayModes.forEach(mode=>mode.addEventListener?.('change',update));
    window.addEventListener('pageshow',update);
    window.addEventListener('popstate',update);
    window.navigation?.addEventListener('currententrychange',update);
    update();
})();
