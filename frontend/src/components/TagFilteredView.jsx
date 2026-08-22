import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { getArticles } from "../api";

export default function TagFilteredView() {
  const { tag } = useParams();
  const [searchParams] = useSearchParams();
  const year = searchParams.get("year");
  const [articles, setArticles] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setArticles(null);
    setError(null);
    getArticles(tag, year || undefined).then(setArticles).catch((err) => setError(err.message));
  }, [tag, year]);

  if (error) return <p>載入失敗，請稍後再試。</p>;
  if (articles === null) return <p>載入中...</p>;

  const backTo = year
    ? `/tag/${encodeURIComponent(tag)}?year=${encodeURIComponent(year)}`
    : `/tag/${encodeURIComponent(tag)}`;

  return (
    <>
      <h1>標籤：{tag}{year ? ` · ${year}` : ""}（{articles.length} 篇）</h1>
      <p><Link to="/tags">&laquo; 返回標籤列表</Link></p>
      <ul>
        {articles.map((a) => (
          <li key={a.nid}>
            <Link to={`/article/${a.nid}`} state={{ from: backTo }}>{a.date} — {a.title}</Link>
          </li>
        ))}
      </ul>
    </>
  );
}
