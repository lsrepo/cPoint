import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getArticles } from "../api";

export default function TagFilteredView() {
  const { tag } = useParams();
  const [articles, setArticles] = useState(null);

  useEffect(() => {
    setArticles(null);
    getArticles(tag).then(setArticles);
  }, [tag]);

  if (articles === null) return <p>載入中...</p>;

  return (
    <>
      <h1>標籤：{tag}（{articles.length} 篇）</h1>
      <p><Link to="/tags">&laquo; 返回標籤列表</Link></p>
      <ul>
        {articles.map((a) => (
          <li key={a.nid}>
            <Link to={`/article/${a.nid}`}>{a.date} — {a.title}</Link>
          </li>
        ))}
      </ul>
    </>
  );
}
