'use strict';

const { retry } = require('fxt-retry');

async function runJob(job, options = {}) {
  const result = await retry(() => job.run(), {
    retries: options.retries ?? 2,
    delayMs: options.delayMs ?? 50,
  });
  return { id: job.id, result };
}

module.exports = { runJob };
