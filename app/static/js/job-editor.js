document.addEventListener('DOMContentLoaded', () => {
    const $ = window.jQuery;
    if (!$ || !$.fn.summernote) return; // Textareas remain usable if the CDN is unavailable.
    $('.job-rich-editor').each(function () {
        const textarea = this;
        if (!/<[a-z][^>]*>/i.test(textarea.value)) {
            const plain = document.createElement('div');
            plain.textContent = textarea.value;
            textarea.value = plain.innerHTML.replace(/\n/g, '<br>');
        }
        const label = document.querySelector(`label[for="${textarea.id}"]`);
        $(textarea).summernote({
            height: textarea.id === 'description' ? 240 : 180,
            minHeight: 120,
            placeholder: textarea.placeholder,
            dialogsInBody: true,
            disableDragAndDrop: true,
            styleTags: ['p', 'h2', 'h3', 'h4', 'blockquote', 'pre'],
            toolbar: [
                ['style', ['style']],
                ['font', ['bold', 'italic', 'underline', 'strikethrough', 'clear']],
                ['paragraph', ['ul', 'ol']],
                ['insert', ['link', 'hr']],
                ['history', ['undo', 'redo']],
                ['view', ['fullscreen']]
            ],
            callbacks: {
                onInit() {
                    $(textarea).next('.note-editor').find('.note-editable')
                        .attr('role', 'textbox').attr('aria-multiline', 'true')
                        .attr('aria-label', label ? label.textContent : textarea.name);
                },
                onImageUpload() { /* Job descriptions accept text and links. */ },
                onChange(contents) { textarea.value = contents; }
            }
        });
        if (label) label.addEventListener('click', () => $(textarea).summernote('focus'));
        textarea.form.addEventListener('submit', () => {
            textarea.value = $(textarea).summernote('isEmpty') ? '' : $(textarea).summernote('code');
        });
    });
});
