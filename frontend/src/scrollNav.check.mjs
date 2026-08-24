#!/usr/bin/env node
// Plain script, no test framework — mirrors the ../checks/*.py convention.
// Run with: node frontend/src/scrollNav.check.mjs
import { nextParagraphIndex } from "./scrollNav.js";

function main() {
  // at the very top of the article: first paragraph is the target
  assertEq(nextParagraphIndex([517, 843, 1035]), 0);

  // scrolled so paragraph 0 is above the viewport already: paragraph 1 is next
  assertEq(nextParagraphIndex([-200, 300, 900]), 1);

  // right at a paragraph boundary (top === threshold): not "below" yet, skip it
  assertEq(nextParagraphIndex([10, 300]), 1);

  // already past every paragraph: nothing to jump to
  assertEq(nextParagraphIndex([-900, -400, -50]), -1);

  // no paragraphs at all
  assertEq(nextParagraphIndex([]), -1);

  console.log("OK: scrollNav.nextParagraphIndex behaves correctly");
}

function assertEq(actual, expected) {
  if (actual !== expected) {
    throw new Error(`expected ${expected}, got ${actual}`);
  }
}

main();
