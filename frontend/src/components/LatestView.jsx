import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { getArticles } from "../api";

export default function LatestView() {
  const [articles, setArticles] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getArticles().then(setArticles).catch((err) => setError(err.message));
  }, []);

  if (error) return <p>載入失敗，請稍後再試。</p>;
  if (articles === null) return <p>載入中...</p>;
  if (articles.length === 0) return <p>找不到文章。</p>;

  // getArticles() is already ordered by date DESC (see db.list_articles).
  const latest = articles[0];
  return (
    <Navigate
      to={`/article/${latest.nid}`}
      state={{ from: "/latest", autoPlayAudio: true }}
      replace
    />
  );
}
