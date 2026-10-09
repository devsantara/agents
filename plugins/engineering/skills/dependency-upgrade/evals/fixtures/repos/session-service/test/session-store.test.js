'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { createSessionStore, THIRTY_MINUTES } = require('../src/session-store');

function clock(start = 1_000_000) {
  let current = start;
  return { now: () => current, advance: (ms) => { current += ms; } };
}

test('loads a saved session', () => {
  const store = createSessionStore();
  store.save('s1', { userId: 7 });
  assert.deepEqual(store.load('s1'), { userId: 7 });
  assert.equal(store.load('missing'), null);
});

test('a session is inactive once it expires', () => {
  const time = clock();
  const store = createSessionStore({ now: time.now });
  store.save('s1', { userId: 7 });
  assert.equal(store.isActive('s1'), true);
  time.advance(THIRTY_MINUTES + 1);
  assert.equal(store.isActive('s1'), false);
  assert.equal(store.load('s1'), null);
});

test('ending a session removes it', () => {
  const store = createSessionStore();
  store.save('s1', { userId: 7 });
  assert.equal(store.end('s1'), true);
  assert.equal(store.isActive('s1'), false);
});
