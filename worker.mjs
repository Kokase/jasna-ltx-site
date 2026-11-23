import app from './dist/worker/index.js';
import { runScheduledSync } from './functions/_lib/sync-schedule.mjs';

export default {
  fetch: app.fetch,
  scheduled: runScheduledSync,
};
