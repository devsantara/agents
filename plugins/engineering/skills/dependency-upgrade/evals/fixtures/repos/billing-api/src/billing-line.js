'use strict';

const { formatMoney } = require('@fxtcorp/money');
const { slugify } = require('fxt-slugkit');

function billingLine(item) {
  return {
    key: slugify(item.description),
    description: item.description,
    total: formatMoney(item.unitCents * item.quantity, item.currency),
  };
}

module.exports = { billingLine };
