'use strict';

const { Cache } = require('fxt-cache');

const THIRTY_MINUTES = 30 * 60 * 1000;

function createSessionStore(options = {}) {
  const cache = new Cache({ maxAge: THIRTY_MINUTES, max: 5000, now: options.now });

  return {
    save(sessionId, session) {
      cache.set(sessionId, session);
    },

    load(sessionId) {
      return cache.fetch(sessionId) ?? null;
    },

    isActive(sessionId) {
      // Workaround: cache.has() returns true for entries that have already
      // expired (fxt-cache issue #41), so read the entry instead of trusting has().
      return cache.fetch(sessionId) !== undefined;
    },

    end(sessionId) {
      return cache.delete(sessionId);
    },
  };
}

module.exports = { createSessionStore, THIRTY_MINUTES };
