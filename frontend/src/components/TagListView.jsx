import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getTags, getYears } from "../api";

export default function TagListView() {
  const [years, setYears] = useState([]);
  const [year, setYear] = useState("");
  const [tags, setTags] = useState(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    getYears().then(setYears).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setTags(null);
    setError(null);
    getTags(year || undefined).then(setTags).catch((err) => setError(err.message));
  }, [year]);

  if (error) return <p>載入失敗，請稍後再試。</p>;

  return (
    <>
      <h1>依標籤瀏覽</h1>
      <select
        className="tag-filter"
        value={year}
        onChange={(e) => setYear(e.target.value)}
      >
        <option value="">全部年份</option>
        {years.map((y) => (
          <option key={y} value={y}>{y}</option>
        ))}
      </select>
      <input
        className="tag-filter"
        type="text"
        placeholder="搜尋標籤..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {tags === null ? (
        <p>載入中...</p>
      ) : (
        <>
          <p>共 {tags.length} 個標籤</p>
          <ul>
            {tags.filter((t) => t.tag.includes(query)).map(({ tag, count }) => (
              <li key={tag}>
                <Link to={`/tag/${encodeURIComponent(tag)}`}>{tag}</Link>（{count}）
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
