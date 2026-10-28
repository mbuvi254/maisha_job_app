const assert = require('node:assert/strict');
const feedback = require('../app/static/js/interview-feedback.js');
const example = 'The candidate demonstrated a strong understanding. Strengths: 1) Thorough validation checks; 2) Clear explanation of time and space complexity; 3) Comprehensive tests. Areas for improvement: 1) Discuss full-stack integration; 2) Discuss alternative data structures.';
let sections = feedback.parse(example);
assert.equal(sections.length,3);
assert.equal(sections[0].title,'');
assert.equal(sections[1].title,'Strengths');
assert.equal(sections[1].kind,'strengths');
assert.equal(sections[2].title,'Areas for improvement');
assert.equal(sections[2].kind,'improvements');
assert.equal(feedback.parse('Still waiting for feedback.')[0].text,'Still waiting for feedback.');
assert.equal(feedback.parse('**Strengths:**\n1. Good checks\n2. Good tests\n**Areas of improvement:**\n1. Explain complexity')[1].kind,'improvements');
// Minimal DOM verifies safe text rendering and numbered-list conversion without a browser dependency.
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.classList={add(){}};this.textContent=''}
 append(child){this.children.push(child)}
 replaceChildren(child){this.children=[child]}
}
global.document = {createElement:tag=>new Element(tag),createDocumentFragment:()=>new Element('fragment')};
const target=new Element('div');
feedback.render(target,example);
assert.equal(target.children[0].children[1].children[1].tag,'ul');
assert.equal(target.children[0].children[1].children[1].children.length,3);
feedback.render(target,'Strengths: 1) <img src=x onerror=alert(1)>');
assert.equal(target.children[0].children[0].children[1].children[0].textContent,'<img src=x onerror=alert(1)>');
console.log('Feedback parsing, numbered lists, legacy text, Markdown labels and safe rendering passed.');
