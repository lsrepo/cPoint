import { useEffect, useRef, useState } from "react";

const LANGS = [
  { value: "cmn", label: "普通話" },
  { value: "yue", label: "粵語" },
];

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

export default function ArticleAudioPlayer({ nid, autoPlay = false }) {
  const audioRef = useRef(null);
  const shouldPlayRef = useRef(autoPlay);
  const userPausedRef = useRef(false);
  const [lang, setLang] = useState("cmn");
  const [status, setStatus] = useState("idle"); // idle | loading | playing | paused | error
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [blocked, setBlocked] = useState(false);

  useEffect(() => {
    setStatus("idle");
    setCurrentTime(0);
    setDuration(0);
    setBlocked(false);
    shouldPlayRef.current = autoPlay;
    // Only re-arm autoplay when the article itself changes, not on every
    // parent re-render — autoPlay is a mount-time intent, not a live prop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nid]);

  useEffect(() => {
    const audio = audioRef.current;
    audio.load();
    if (!shouldPlayRef.current) return;
    shouldPlayRef.current = false;
    setStatus("loading");
    // Chrome only ever grants "muted playback may autoplay with no user
    // gesture" to elements with a video track -- confirmed empirically,
    // including against the engine's own default policy for a fresh
    // visitor with no engagement history (which is why the cached file
    // is an MP4 with a minimal video track, not a bare audio file — see
    // tts.py). Starting muted and immediately unmuting once playback has
    // begun reliably produces real audible playback: unmuting an
    // already-playing element doesn't itself require a gesture. This
    // must be the FIRST play() attempt on the element, muted or not: a
    // failed unmuted attempt poisons every later attempt (even muted
    // ones) on that same element for a cooldown period, also confirmed
    // empirically -- so never try unmuted first here.
    audio.muted = true;
    audio.play()
      .then(() => {
        setStatus("playing");
        setBlocked(false);
        audio.muted = false;
      })
      .catch(() => setBlocked(true));
  }, [nid, lang]);

  const handleTogglePlay = () => {
    const audio = audioRef.current;
    setBlocked(false);
    if (status === "playing") {
      userPausedRef.current = true;
      audio.pause();
      setStatus("paused");
      return;
    }
    setStatus("loading");
    audio.muted = false;
    audio.play().then(() => setStatus("playing")).catch(() => setStatus("error"));
  };

  const handleSeek = (e) => {
    const t = Number(e.target.value);
    audioRef.current.currentTime = t;
    setCurrentTime(t);
  };

  const handleLangChange = (e) => {
    shouldPlayRef.current = status === "playing" || status === "loading";
    setLang(e.target.value);
  };

  const progressPct = duration ? (currentTime / duration) * 100 : 0;

  return (
    <div className="audio-player">
      {/* A <video> element, not <audio>: Chrome's autoplay policy only
          ever exempts elements with a video track from needing a user
          gesture before muted playback can start -- see tts.py and the
          autoplay effect above. The cached file is an MP4 with a
          minimal (2x2px) video track for exactly this reason. Visually
          hidden rather than display:none, since some browsers throttle
          or pause genuinely display:none media. */}
      <video
        ref={audioRef}
        src={`/api/article/${nid}/audio/${lang}`}
        preload="none"
        style={{ position: "absolute", width: 1, height: 1, opacity: 0, pointerEvents: "none" }}
        onPlaying={() => setStatus("playing")}
        onPause={(e) => {
          if (userPausedRef.current) { userPausedRef.current = false; return; }
          if (e.currentTarget.ended) return; // natural end -- onEnded handles this
          // Chrome silently paused this out from under us: it detected the
          // muted-autoplay-then-unmute attempt above and reverted it because
          // this visitor has never interacted with the site before. Surface
          // the fallback button rather than leaving the UI claiming "playing".
          setStatus("idle");
          setBlocked(true);
        }}
        onEnded={() => setStatus("idle")}
        onError={() => setStatus("error")}
        onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
        onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
      />
      <select
        className="audio-player-lang"
        value={lang}
        onChange={handleLangChange}
        aria-label="朗讀語言"
      >
        {LANGS.map((l) => (
          <option key={l.value} value={l.value}>{l.label}</option>
        ))}
      </select>
      <button
        type="button"
        className="audio-player-toggle"
        onClick={handleTogglePlay}
        disabled={status === "loading"}
        aria-label={status === "playing" ? "暫停" : "播放"}
      >
        {status === "playing" ? "❚❚" : status === "loading" ? "…" : "▶"}
      </button>
      <span className="audio-player-time">{formatTime(currentTime)}</span>
      <input
        type="range"
        className="audio-player-seek"
        style={{ "--progress": `${progressPct}%` }}
        min={0}
        max={duration || 0}
        step={0.1}
        value={currentTime}
        onChange={handleSeek}
        disabled={!duration}
        aria-label="播放進度"
      />
      <span className="audio-player-time">{formatTime(duration)}</span>
      {status === "error" && <span className="audio-player-unavailable">語音載入失敗</span>}
      {blocked && (
        <button type="button" className="audio-player-autoplay-fallback" onClick={handleTogglePlay}>
          ▶ 播放
        </button>
      )}
    </div>
  );
}
