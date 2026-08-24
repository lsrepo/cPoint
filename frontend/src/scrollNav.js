// Pure logic for "ArrowDown jumps to the next paragraph" (ArticleView.jsx).
// Kept separate from the component so it's testable without a DOM/browser.

// `tops` is each paragraph's current distance from the viewport top (as
// DOMRect.top would report). Returns the index of the first paragraph
// below the top of the viewport, or -1 if every paragraph is already
// scrolled past (nothing left to jump to).
export function nextParagraphIndex(tops, threshold = 10) {
  return tops.findIndex((top) => top > threshold);
}
