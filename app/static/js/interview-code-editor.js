/* Keep the original textarea as the source of truth and accessible fallback. */
window.createInterviewCodeEditor = function (textarea, language) {
    const shell = document.getElementById('codeEditorShell');
    const host = document.getElementById('codeEditor');
    const fallback = document.getElementById('plainCodeEditor');
    const status = document.getElementById('codeEditorStatus');
    let editor = null, coding = false, locked = false;
    const modes = { python:'python', py:'python', javascript:'javascript', js:'javascript', typescript:'typescript', ts:'typescript', java:'java', 'c++':'c_cpp', cpp:'c_cpp', c:'c_cpp', 'c#':'csharp', csharp:'csharp', sql:'sql', go:'golang', golang:'golang', rust:'rust', php:'php', ruby:'ruby', kotlin:'kotlin', swift:'swift', html:'html', css:'css', bash:'sh' };
    function syncMode() {
        const mode = modes[language.value.trim().toLowerCase()] || 'text';
        if (editor) editor.session.setMode('ace/mode/' + mode);
        document.getElementById('codeEditorLanguage').textContent = language.value || 'Plain text';
    }
    function update() {
        const enhanced = coding && !!editor && !fallback.checked;
        shell.hidden = !enhanced;
        textarea.hidden = enhanced;
        textarea.required = !enhanced;
        textarea.readOnly = locked;
        if (editor) { editor.setReadOnly(locked); if (enhanced) editor.resize(); }
        status.textContent = locked ? 'Submitted · read only' : editor ? 'Code editor ready' : 'Plain text editor · syntax highlighting unavailable';
    }
    function initialize() {
        if (!coding || editor || !window.ace) return;
        try {
            window.ace.config.set('basePath', 'https://cdn.jsdelivr.net/npm/ace-builds@1.36.2/src-min-noconflict');
            editor = window.ace.edit(host);
            editor.setOptions({ fontSize:14, showPrintMargin:false, tabSize:4, useSoftTabs:true, highlightActiveLine:true, displayIndentGuides:true });
            editor.commands.addCommand({ name:'leaveInterviewEditor', bindKey:{win:'Esc',mac:'Esc'}, exec:()=>fallback.focus() });
            const input = host.querySelector('textarea');
            if (input) { input.setAttribute('aria-label', 'Code solution'); input.setAttribute('aria-describedby', 'codeEditorHint'); }
            editor.session.setUseWorker(false);
            editor.session.setUseWrapMode(true);
            editor.setValue(textarea.value, -1);
            editor.session.on('change', () => { textarea.value = editor.getValue(); });
            syncMode();
            theme();
        } catch (_) { if (editor) editor.destroy(); editor=null; }
    }
    function theme() { if (editor) editor.setTheme(document.documentElement.dataset.bsTheme === 'dark' ? 'ace/theme/tomorrow_night' : 'ace/theme/textmate'); }
    language.addEventListener('input', syncMode);
    textarea.addEventListener('input', () => { if (editor && textarea.value !== editor.getValue()) editor.setValue(textarea.value, -1); });
    fallback.addEventListener('change', () => { if (editor && textarea.value !== editor.getValue()) editor.setValue(textarea.value, -1); update(); });
    document.getElementById('aceLibrary').addEventListener('load', () => { initialize(); update(); });
    new MutationObserver(theme).observe(document.documentElement, { attributes:true, attributeFilter:['data-bs-theme'] });
    return {
        setQuestion(isCoding) { coding=isCoding; locked=false; if(coding) initialize(); if(editor) editor.setValue(textarea.value, -1); update(); },
        lock(value=true) { locked=value; update(); },
        value() { return textarea.value; }
    };
};
