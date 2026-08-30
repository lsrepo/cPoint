import { useEffect, useState } from "react";
import { getVocab } from "../api";

function speak(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-GB";
  window.speechSynthesis.speak(utterance);
}

export default function EnglishCorner({ nid }) {
  const [terms, setTerms] = useState(undefined);
  const speechSupported = typeof window !== "undefined" && "speechSynthesis" in window;

  useEffect(() => {
    setTerms(undefined);
    let cancelled = false;
    getVocab(nid)
      .then((data) => { if (!cancelled) setTerms(data); })
      .catch(() => { if (!cancelled) setTerms([]); });
    return () => { cancelled = true; };
  }, [nid]);

  if (terms === undefined) {
    return (
      <section className="vocab-corner">
        <h2 className="vocab-corner-title">英文學習角</h2>
        <p className="vocab-corner-loading">生字載入中...</p>
      </section>
    );
  }
  if (terms.length === 0) return null;

  return (
    <section className="vocab-corner">
      <h2 className="vocab-corner-title">英文學習角</h2>
      <ul className="vocab-list">
        {terms.map((t) => (
          <li key={t.term} className="vocab-item">
            <div className="vocab-item-head">
              <span className="vocab-term">{t.term}</span>
              <span className="vocab-pos">{t.pos}</span>
              <span className="vocab-ipa">{t.ipa}</span>
              {speechSupported && (
                <button
                  type="button"
                  className="vocab-play-btn"
                  aria-label={`播放 ${t.term} 發音`}
                  onClick={() => speak(t.term)}
                >
                  播放
                </button>
              )}
              <span className="vocab-zh">對應：{t.zh}</span>
            </div>
            <p className="vocab-example">{t.example}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
