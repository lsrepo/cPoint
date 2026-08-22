import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { getArticle } from "../api";

export default function ArticleView() {
  const { nid } = useParams();
  const location = useLocation();
  const backTo = location.state?.from || "/date";
  const [article, setArticle] = useState(undefined);
  const [error, setError] = useState(null);

  useEffect(() => {
    setArticle(undefined);
    setError(null);
    getArticle(nid).then(setArticle).catch((err) => setError(err.message));
  }, [nid]);

  if (error) return <p>載入失敗，請稍後再試。</p>;
  if (article === undefined) return <p>載入中...</p>;
  if (article === null) return <p>找不到文章。</p>;

  return (
    <>
      <p><Link to={backTo}>&laquo; 返回文章列表</Link></p>
      <h1>{article.title}</h1>
      <p className="meta">
        {article.date} ·{" "}
        <a href={article.url} target="_blank" rel="noopener noreferrer">原文連結</a>
      </p>
      <p className="tags">
        {article.hashtags.map((t) => (
          <Link key={t} className="tag" to={`/tag/${encodeURIComponent(t)}`}>{t}</Link>
        ))}
      </p>
      {article.body.split("\n\n").map((para, i) => (
        <p key={i}>{para}</p>
      ))}
    </>
  );
}
