export async function getArticles(tag) {
  const url = tag ? `/api/articles?tag=${encodeURIComponent(tag)}` : "/api/articles";
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} failed: ${res.status}`);
  return res.json();
}

export async function getTags(year) {
  const url = year ? `/api/tags?year=${encodeURIComponent(year)}` : "/api/tags";
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} failed: ${res.status}`);
  return res.json();
}

export async function getYears() {
  const res = await fetch("/api/years");
  if (!res.ok) throw new Error(`GET /api/years failed: ${res.status}`);
  return res.json();
}

export async function getArticle(nid) {
  const res = await fetch(`/api/article/${nid}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GET /api/article/${nid} failed: ${res.status}`);
  return res.json();
}
