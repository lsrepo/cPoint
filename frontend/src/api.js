export async function getArticles(tag) {
  const url = tag ? `/api/articles?tag=${encodeURIComponent(tag)}` : "/api/articles";
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} failed: ${res.status}`);
  return res.json();
}

export async function getTags() {
  const res = await fetch("/api/tags");
  if (!res.ok) throw new Error(`GET /api/tags failed: ${res.status}`);
  return res.json();
}

export async function getArticle(nid) {
  const res = await fetch(`/api/article/${nid}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GET /api/article/${nid} failed: ${res.status}`);
  return res.json();
}
