# Cantonese Audio Player — Design

## Background

The user wants to listen to "C觀點" articles read aloud in Cantonese,
via a player shown before the article body on the article page
([ArticleView.jsx](../../../frontend/src/components/ArticleView.jsx)).

Cloud TTS providers (Azure AI Speech, Google Cloud TTS's Chirp 3 HD) both
now offer genuine `zh-HK`/`yue-HK` Cantonese neural voices, not just
Mandarin reads of the same characters — but they cost money past a free
tier and need a backend generation/caching pipeline (an API key, a call
to an external service, disk or object storage for generated audio).
Self-hosted open-source Cantonese TTS (e.g. CosyVoice2) avoids per-call
cost but is a multi-GB ML model needing real compute — impractical on
this project's deployment target (Render's free tier: no GPU, minimal
CPU/RAM) and a large departure from this repo's stdlib-only,
framework-minimal conventions ([AGENTS.md](../../../AGENTS.md)).

macOS ships a genuine Cantonese system voice ("Sinji", locale `zh_HK`),
which is also exposed to browsers running on macOS/iOS through the
standard Web Speech API (`window.speechSynthesis`) — no server
involvement, no API key, no cost. The user chose this path: a
purely client-side player that uses whichever Cantonese voice the
visitor's own browser/OS provides, with no fallback to a
mispronounced Mandarin voice if none is available.

## Functional Requirements

- **FR1 — Player placement.** A player is shown on the article page,
  after the title/meta/tags block and before the article body
  (`<div className="article-body">`).
- **FR2 — Cantonese voice detection.** On mount, the player inspects
  `speechSynthesis.getVoices()` for a voice whose `lang` starts with
  `zh-HK` or `yue` (covers both Sinji's `zh-HK` tag and any browser
  using a `yue-HK` tag). Chrome populates the voice list asynchronously,
  so the player also listens once for the `voiceschanged` event and
  re-checks.
- **FR3 — No-voice fallback.** If `window.speechSynthesis` doesn't
  exist, or no matching Cantonese voice is found once the check has
  settled, the player renders a small muted line — "此瀏覽器沒有粵語語音"
  — instead of playback controls. It must never fall back to reading
  the article in a Mandarin (or other) voice.
- **FR4 — Playback content.** The player reads the article body only
  (not the title, not the hashtags).
- **FR5 — Paragraph-by-paragraph queueing.** The body is split the same
  way it's already rendered (`body.split("\n\n")`), and each paragraph
  becomes its own `SpeechSynthesisUtterance`, submitted to
  `speechSynthesis.speak()` in order. The browser plays a queue of
  utterances sequentially on its own — the player does not need to wait
  for one utterance's `end` event before queueing the next.
- **FR6 — Controls.** Play, Pause/Resume, and Stop, backed directly by
  `speechSynthesis.speak()` / `.pause()` / `.resume()` / `.cancel()`.
  The player tracks only enough state to know which buttons are valid
  (`idle | playing | paused`) — no custom scrubbing, no progress bar.
- **FR7 — Stop on navigation.** Leaving the article (route/`nid`
  change) or unmounting the component cancels any in-progress or queued
  speech (`speechSynthesis.cancel()`), so audio never continues over a
  different article.

## Non-Functional Requirements

- **NFR1 — Zero backend footprint.** No new API routes, no new
  dependencies in `requirements.txt`, no changes to `db.py` or the data
  pipeline. This is a frontend-only addition.
- **NFR2 — No added frontend dependencies.** Implemented with the
  browser's native `SpeechSynthesis`/`SpeechSynthesisUtterance` APIs
  only — no new npm packages, consistent with this repo's
  framework-minimal frontend convention.
- **NFR3 — Fails silent, not wrong.** Because voice availability is
  entirely device-dependent, the player must never guess or
  silently substitute a non-Cantonese voice. Unsupported/unavailable
  is always shown as unavailable (FR3), never worked around.

## Component

A new `frontend/src/components/CantoneseAudioPlayer.jsx`, taking the
article's `body` string as its only prop. `ArticleView.jsx` renders it
between the tags block and the article body, keyed (or reset) on `nid`
the same way `ArticleView`'s own effect already resets on `nid` change.

## Out of Scope

- Reading the title or hashtags aloud.
- Word/sentence highlighting synced to playback (`boundary` events) —
  noted as a possible future enhancement, not part of this design.
- Any server-generated audio, caching, or non-macOS/iOS voice sourcing.
- A settings/voice-picker UI — the player uses the first matching
  Cantonese voice found, with no user-facing choice between voices.

## Testing

There is no backend/API surface to exercise, so `checks/*.py` and
`npm run lint` are unaffected by this change. Verification is manual:

- On a browser/OS with a Cantonese voice (e.g. Safari on macOS, where
  Sinji is installed): open an article, confirm Play starts audio,
  Pause/Resume and Stop work, and paragraphs play in order without
  gaps or overlap.
- On a browser/OS without a Cantonese voice (e.g. Chrome without one
  installed): confirm the fallback message appears and no playback
  controls are shown.
- Navigate away from an article mid-playback and confirm audio stops
  rather than continuing over the next page.
