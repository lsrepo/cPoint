import { useEffect, useState } from "react";
import { HashRouter, Routes, Route, Navigate, Link, useLocation } from "react-router-dom";
import "./index.css";
import DateView from "./components/DateView";
import TagListView from "./components/TagListView";
import TagFilteredView from "./components/TagFilteredView";
import ArticleView from "./components/ArticleView";

const THEME_KEY = "theme";

function getInitialTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function ThemeToggle() {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
    >
      {theme === "dark" ? "☀️ 淺色" : "🌙 深色"}
    </button>
  );
}

function NavToggle() {
  const location = useLocation();
  const isTags = location.pathname.startsWith("/tag");
  return (
    <nav className="nav-toggle">
      依 <Link to="/date" className={isTags ? "" : "active"}>日期</Link>
      <span className="nav-toggle-sep">/</span>
      <Link to="/tags" className={isTags ? "active" : ""}>標籤</Link> 瀏覽
    </nav>
  );
}

export default function App() {
  return (
    <HashRouter>
      <header>
        <h1 className="site-title">「C觀點」文章庫</h1>
        <NavToggle />
        <ThemeToggle />
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/date" replace />} />
          <Route path="/date" element={<DateView />} />
          <Route path="/tags" element={<TagListView />} />
          <Route path="/tag/:tag" element={<TagFilteredView />} />
          <Route path="/article/:nid" element={<ArticleView />} />
        </Routes>
      </main>
    </HashRouter>
  );
}
