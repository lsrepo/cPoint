const DISPATCH_URL =
  "https://api.github.com/repos/lsrepo/cpoint/actions/workflows/sync-articles.yml/dispatches";

export default {
  async scheduled(_event, env) {
    const token = env.GITHUB_TOKEN;
    if (!token) {
      throw new Error("GITHUB_TOKEN is not set");
    }

    const res = await fetch(DISPATCH_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "cpoint-sync-tick",
      },
      body: JSON.stringify({ ref: "main" }),
    });

    if (!res.ok) {
      const detail = (await res.text()).slice(0, 300);
      throw new Error(`dispatch ${res.status} ${detail}`);
    }
  },
};
