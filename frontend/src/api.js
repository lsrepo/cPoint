export async function getArticles(tag) {
  const url = tag ? `/api/articles?tag=${encodeURIComponent(tag)}` : "/api/articles";
  const res = await fetch(url);
  return res.json();
}

export async function getTags() {
  const res = await fetch("/api/tags");
  return res.json();
}

export async function getArticle(nid) {
  const res = await fetch(`/api/article/${nid}`);
  if (!res.ok) return null;
  return res.json();
}
