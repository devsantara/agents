'use strict';

const { slugify } = require('fxt-slugkit');

function productSlug(product) {
  if (typeof product.name !== 'string' || product.name.trim() === '') {
    throw new TypeError('product.name must be a non-empty string');
  }
  return slugify(product.name);
}

module.exports = { productSlug };
