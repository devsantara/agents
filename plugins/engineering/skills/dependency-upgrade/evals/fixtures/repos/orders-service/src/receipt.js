'use strict';

const datefmt = require('fxt-datefmt');

const RECEIPT_PATTERN = 'YYYY-MM-DD HH:mm';

function buildReceipt(payment) {
  return {
    reference: payment.reference,
    paidAt: datefmt.formatDate(new Date(payment.paidAt), RECEIPT_PATTERN),
    amountCents: payment.amountCents,
  };
}

module.exports = { buildReceipt };
