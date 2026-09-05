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
    audio.play()
      .then(() => { setStatus("playing"); setBlocked(false); })
      .catch(() => setBlocked(true));
  }, [nid, lang]);

  const handleTogglePlay = () => {
    const audio = audioRef.current;
    setBlocked(false);
    if (status === "playing") {
      audio.pause();
      setStatus("paused");
      return;
    }
    setStatus("loading");
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
      <audio
        ref={audioRef}
        src={`/api/article/${nid}/audio/${lang}`}
        preload="none"
        onPlaying={() => setStatus("playing")}
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
