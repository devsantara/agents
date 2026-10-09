'use strict';

const { render } = require('fxt-mdlite');

function renderPage(page) {
  return `<article data-slug="${page.slug}">\n${render(page.markdown)}\n</article>`;
}

module.exports = { renderPage };
