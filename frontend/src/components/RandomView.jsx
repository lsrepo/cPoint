import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { getArticles } from "../api";

export function pickRandom(articles) {
  return articles[Math.floor(Math.random() * articles.length)];
}

export default function RandomView() {
  const [articles, setArticles] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getArticles().then(setArticles).catch((err) => setError(err.message));
  }, []);

  if (error) return <p>載入失敗，請稍後再試。</p>;
  if (articles === null) return <p>載入中...</p>;
  if (articles.length === 0) return <p>找不到文章。</p>;

  const target = pickRandom(articles);
  return <Navigate to={`/article/${target.nid}`} state={{ from: "/random" }} replace />;
}
