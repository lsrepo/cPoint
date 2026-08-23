import { useEffect, useState } from "react";

function findCantoneseVoice() {
  return window.speechSynthesis.getVoices().find((v) => {
    const lang = v.lang.toLowerCase();
    return lang.startsWith("zh-hk") || lang.startsWith("yue");
  });
}

export default function CantoneseAudioPlayer({ body }) {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const [voice, setVoice] = useState(() => (supported ? findCantoneseVoice() : undefined));
  const [state, setState] = useState("idle"); // idle | playing | paused

  useEffect(() => {
    if (!supported || voice) return;
    const onVoicesChanged = () => setVoice(findCantoneseVoice());
    window.speechSynthesis.addEventListener("voiceschanged", onVoicesChanged);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", onVoicesChanged);
  }, [supported, voice]);

  useEffect(() => {
    setState("idle");
    return () => {
      if (supported) window.speechSynthesis.cancel();
    };
  }, [body, supported]);

  if (!voice) return <p className="audio-player-unavailable">此瀏覽器沒有粵語語音</p>;

  const handlePlay = () => {
    if (state === "paused") {
      window.speechSynthesis.resume();
      setState("playing");
      return;
    }
    window.speechSynthesis.cancel();
    const paragraphs = body.split("\n\n").filter((p) => p.trim());
    paragraphs.forEach((text, i) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = voice;
      utterance.lang = voice.lang;
      if (i === paragraphs.length - 1) {
        utterance.onend = () => setState("idle");
        utterance.onerror = () => setState("idle");
      }
      window.speechSynthesis.speak(utterance);
    });
    setState("playing");
  };

  const handlePause = () => {
    window.speechSynthesis.pause();
    setState("paused");
  };

  const handleStop = () => {
    window.speechSynthesis.cancel();
    setState("idle");
  };

  return (
    <div className="audio-player">
      {state === "playing" ? (
        <button type="button" onClick={handlePause}>暫停</button>
      ) : (
        <button type="button" onClick={handlePlay}>
          {state === "paused" ? "繼續" : "粵語朗讀"}
        </button>
      )}
      <button type="button" onClick={handleStop} disabled={state === "idle"}>停止</button>
    </div>
  );
}
