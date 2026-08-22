import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getTags } from "../api";

export default function TagListView() {
  const [tags, setTags] = useState(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    getTags().then(setTags).catch((err) => setError(err.message));
  }, []);

  if (error) return <p>載入失敗，請稍後再試。</p>;
  if (tags === null) return <p>載入中...</p>;

  const filtered = tags.filter((t) => t.tag.includes(query));

  return (
    <>
      <h1>依標籤瀏覽</h1>
      <input
        className="tag-filter"
        type="text"
        placeholder="搜尋標籤..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <p>共 {tags.length} 個標籤</p>
      <ul>
        {filtered.map(({ tag, count }) => (
          <li key={tag}>
            <Link to={`/tag/${encodeURIComponent(tag)}`}>{tag}</Link>（{count}）
          </li>
        ))}
      </ul>
    </>
  );
}
