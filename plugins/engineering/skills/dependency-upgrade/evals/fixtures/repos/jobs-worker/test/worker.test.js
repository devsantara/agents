'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { runJob } = require('../src/worker');

test('retries a failing job until it succeeds', async () => {
  let calls = 0;
  const job = {
    id: 'job-1',
    run: async () => {
      calls += 1;
      if (calls < 3) throw new Error('flaky');
      return 'ok';
    },
  };
  assert.deepEqual(await runJob(job, { delayMs: 1 }), { id: 'job-1', result: 'ok' });
  assert.equal(calls, 3);
});

test('gives up after the configured retries', async () => {
  const job = { id: 'job-2', run: async () => { throw new Error('down'); } };
  await assert.rejects(runJob(job, { retries: 1, delayMs: 1 }), /down/);
});
