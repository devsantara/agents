'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { buildInvoice } = require('../src/invoice');
const { buildReceipt } = require('../src/receipt');
const { productSlug } = require('../src/catalog');

test('invoice carries the issue date and line slugs', () => {
  const invoice = buildInvoice({
    id: 42,
    createdAt: '2025-03-09T10:15:00Z',
    items: [{ name: 'Blue Widget (Large)', quantity: 2 }],
  });
  assert.deepEqual(invoice, {
    number: 'INV-42',
    issuedOn: '2025-03-09',
    lines: [{ sku: 'blue-widget-large', quantity: 2 }],
  });
});

test('receipt formats the payment time to the minute', () => {
  const receipt = buildReceipt({ reference: 'PAY-7', paidAt: '2025-03-09T18:04:59Z', amountCents: 1999 });
  assert.equal(receipt.paidAt, '2025-03-09 18:04');
});

test('product slug rejects a missing name', () => {
  assert.throws(() => productSlug({}), TypeError);
});
