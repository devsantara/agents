'use strict';

const { formatDate } = require('fxt-datefmt');
const { productSlug } = require('./catalog');

function buildInvoice(order) {
  return {
    number: `INV-${order.id}`,
    issuedOn: formatDate(new Date(order.createdAt)),
    lines: order.items.map((item) => ({
      sku: productSlug(item),
      quantity: item.quantity,
    })),
  };
}

module.exports = { buildInvoice };
