import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getArticles } from "../api";

function shortDate(date) {
  const [, month, day] = date.split("-");
  return `${parseInt(day, 10)}/${parseInt(month, 10)}`;
}

function groupByYear(articles) {
  const groups = new Map();
  for (const a of articles) {
    const year = a.date.slice(0, 4);
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year).push(a);
  }
  return Array.from(groups.entries()).sort((a, b) => b[0].localeCompare(a[0]));
}

export default function DateView() {
  const [articles, setArticles] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getArticles().then(setArticles).catch((err) => setError(err.message));
  }, []);

  if (error) return <p>載入失敗，請稍後再試。</p>;
  if (articles === null) return <p>載入中...</p>;

  const groups = groupByYear(articles);
  const currentYear = groups.length ? groups[0][0] : "";

  return (
    <>
      {groups.map(([year, arts]) => (
        <details key={year} open={year === currentYear}>
          <summary>{year}（{arts.length}）</summary>
          <ul>
            {arts.map((a) => (
              <li key={a.nid}>
                <Link className="article-link" to={`/article/${a.nid}`}>{shortDate(a.date)} — {a.title}</Link>
              </li>
            ))}
          </ul>
        </details>
      ))}
    </>
  );
}
