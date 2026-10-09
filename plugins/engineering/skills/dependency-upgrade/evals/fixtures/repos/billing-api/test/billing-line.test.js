'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { billingLine } = require('../src/billing-line');

test('formats a billing line', () => {
  assert.deepEqual(billingLine({ description: 'Pro plan (annual)', unitCents: 4900, quantity: 12, currency: 'USD' }), {
    key: 'pro-plan-annual',
    description: 'Pro plan (annual)',
    total: '$588.00',
  });
});

test('falls back to the currency code for unknown currencies', () => {
  assert.equal(billingLine({ description: 'Seat', unitCents: 1050, quantity: 1, currency: 'SEK' }).total, 'SEK 10.50');
});
