import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getArticle } from "../api";

export default function ArticleView() {
  const { nid } = useParams();
  const [article, setArticle] = useState(undefined);

  useEffect(() => {
    setArticle(undefined);
    getArticle(nid).then(setArticle);
  }, [nid]);

  if (article === undefined) return <p>載入中...</p>;
  if (article === null) return <p>找不到文章。</p>;

  return (
    <>
      <p><Link to="/date">&laquo; 返回文章列表</Link></p>
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
