/* Shared presentation for live and saved feedback. Model text is never inserted as HTML. */
(function (root) {
    function parseFeedback(value) {
        const text = String(value || '').replace(/\r\n/g, '\n');
        const labels = /(?:\*\*|__|#{1,4}\s*)?\b(areas?\s+(?:for|of)\s+improvement|strengths|improvements|recommendations|next steps|overall assessment|summary)\s*(?:\*\*|__)?\s*:\s*(?:\*\*|__)?/gi;
        const matches = Array.from(text.matchAll(labels));
        if (!matches.length) return [{ title: '', kind: 'summary', text: text.trim() }];
        const sections = [];
        if (text.slice(0, matches[0].index).trim()) sections.push({ title: '', kind: 'summary', text: text.slice(0, matches[0].index).trim() });
        matches.forEach((match, i) => {
            const key = match[1].toLowerCase();
            sections.push({
                title: key === 'strengths' ? 'Strengths' : /^areas?|improvements/.test(key) ? 'Areas for improvement' : key.replace(/\b\w/g, c => c.toUpperCase()),
                kind: key === 'strengths' ? 'strengths' : /^areas?|improvements/.test(key) ? 'improvements' : 'summary',
                text: text.slice(match.index + match[0].length, matches[i + 1]?.index ?? text.length).trim()
            });
        });
        return sections;
    }
    function renderFeedback(target, value) {
        const fragment = document.createDocumentFragment();
        for (const section of parseFeedback(value)) {
            const box = document.createElement('section');
            box.className = 'feedback-section feedback-' + section.kind;
            if (section.title) { const heading = document.createElement('h4'); heading.textContent = section.title; box.append(heading); }
            const marker = /(?:^|\s)(?:\d+[.)]|[-•*])\s+/g;
            const items = section.text.split(marker).map(s => s.trim().replace(/;\s*$/, '')).filter(Boolean);
            if (items.length > 1 || /^(?:\d+[.)]|[-•*])\s+/.test(section.text)) {
                const list = document.createElement('ul');
                items.forEach(text => { const item = document.createElement('li'); item.textContent = text; list.append(item); });
                box.append(list);
            } else { const paragraph = document.createElement('p'); paragraph.textContent = section.text; box.append(paragraph); }
            fragment.append(box);
        }
        target.replaceChildren(fragment);
        target.classList.add('structured-feedback');
    }
    root.InterviewFeedback = { parse: parseFeedback, render: renderFeedback };
    if (typeof module !== 'undefined') module.exports = root.InterviewFeedback;
    if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-interview-feedback]').forEach(target => renderFeedback(target, target.textContent));
    });
})(typeof window !== 'undefined' ? window : globalThis);
