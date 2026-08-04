#!/usr/bin/env node
/**
 * CLI wrapper around scripts/bundleBudget.mjs. Run after a build:
 *
 *   pnpm build && pnpm perf:budget
 *
 * Prints the table to stdout always, appends it to the GitHub job summary when
 * running in Actions, and exits 1 if any route is over budget (or unbudgeted).
 * Budgets live in perf-budgets.json — see docs/performance.md for how to move one.
 */

import { appendFile, readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import process from 'node:process';
import { evaluateBudgets, formatSummary, hasFailure, measureDist } from './bundleBudget.mjs';

const root = process.cwd();
const distDir = resolve(root, 'dist');

const budgets = JSON.parse(await readFile(resolve(root, 'perf-budgets.json'), 'utf8'));
const routes = await measureDist(distDir);

if (routes.length === 0) {
  console.error(`No prerendered documents found in ${distDir}. Run \`pnpm build\` first.`);
  process.exit(1);
}

const results = evaluateBudgets(routes, budgets);
const summary = formatSummary(routes, results);

console.log(summary);

if (process.env.GITHUB_STEP_SUMMARY) {
  await appendFile(process.env.GITHUB_STEP_SUMMARY, `${summary}\n`);
}

if (hasFailure(results)) {
  console.error(
    '\nBundle budget check failed. If the growth is intended, raise the budget in ' +
      'perf-budgets.json in the same commit and say why in the message.'
  );
  process.exit(1);
}
