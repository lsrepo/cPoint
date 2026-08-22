import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getArticles } from "../api";

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

  useEffect(() => {
    getArticles().then(setArticles);
  }, []);

  if (articles === null) return <p>載入中...</p>;

  const groups = groupByYear(articles);
  const currentYear = groups.length ? groups[0][0] : "";

  return (
    <>
      <h1>依日期瀏覽</h1>
      {groups.map(([year, arts]) => (
        <details key={year} open={year === currentYear}>
          <summary>{year}（{arts.length}）</summary>
          <ul>
            {arts.map((a) => (
              <li key={a.nid}>
                <Link to={`/article/${a.nid}`}>{a.date} — {a.title}</Link>
              </li>
            ))}
          </ul>
        </details>
      ))}
    </>
  );
}
