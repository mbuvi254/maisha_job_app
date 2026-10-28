window.createInterviewRichEditor = function (answer, explanation, codeEditor) {
    let coding = false, locked = false;
    const active = new Set();
    function mount(textarea, height) {
        const $ = window.jQuery;
        if (!$ || !$.fn.summernote || active.has(textarea)) return;
        $(textarea).summernote({
            height, minHeight:120, dialogsInBody:true, disableDragAndDrop:true, tabDisable:true,
            placeholder:textarea.placeholder, styleTags:['p','h2','h3','blockquote','pre'],
            toolbar:[['style',['style']],['font',['bold','italic','underline','clear']],['paragraph',['ul','ol']],['insert',['link']],['history',['undo','redo']],['view',['fullscreen']]],
            callbacks:{
                onInit() { $(textarea).next('.note-editor').find('.note-editable').attr('role','textbox').attr('aria-multiline','true').attr('aria-label',textarea === answer ? 'Your Answer' : 'Approach, complexity, and test cases'); },
                onChange(html) { textarea.value=html; },
                onImageUpload() {}
            }
        });
        active.add(textarea);
        textarea.required=false;
        $(textarea).summernote(locked ? 'disable' : 'enable');
    }
    function mountCurrent() { mount(coding ? explanation : answer, coding ? 180 : 260); }
    function destroy() {
        for (const textarea of active) window.jQuery(textarea).summernote('destroy');
        active.clear();
    }
    document.getElementById('interviewSummernoteLibrary').addEventListener('load', mountCurrent);
    return {
        setQuestion(isCoding) {
            destroy(); coding=isCoding; locked=false;
            answer.value=''; explanation.value='';
            codeEditor.setQuestion(coding);
            mountCurrent();
        },
        lock(value=true) {
            locked=value; codeEditor.lock(value);
            for(const textarea of active) { textarea.required=false; window.jQuery(textarea).summernote(value ? 'disable' : 'enable'); }
            explanation.readOnly=value;
        },
        value() { return active.has(answer) ? (window.jQuery(answer).summernote('isEmpty') ? '' : window.jQuery(answer).summernote('code')) : codeEditor.value(); },
        explanation() { return active.has(explanation) ? (window.jQuery(explanation).summernote('isEmpty') ? '' : window.jQuery(explanation).summernote('code')) : explanation.value; },
        answerFormat() { return active.has(answer) ? 'html' : 'text'; },
        explanationFormat() { return active.has(explanation) ? 'html' : 'text'; }
    };
};
