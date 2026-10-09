'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { renderPage } = require('../src/render-page');

test('renders headings and paragraphs', () => {
  const html = renderPage({ slug: 'refunds', markdown: '# Refunds\n\nRefunds take **five** days.' });
  assert.equal(html, '<article data-slug="refunds">\n<h1>Refunds</h1>\n<p>Refunds take <strong>five</strong> days.</p>\n</article>');
});

test('escapes HTML in user-written pages', () => {
  const html = renderPage({ slug: 'x', markdown: '<script>alert(1)</script>' });
  assert.ok(html.includes('&lt;script&gt;'));
});
