import { useEffect, useState } from "react";
import { HashRouter, Routes, Route, Navigate, Link, useLocation } from "react-router-dom";
import "./index.css";
import DateView from "./components/DateView";
import TagListView from "./components/TagListView";
import TagFilteredView from "./components/TagFilteredView";
import RandomView from "./components/RandomView";
import LatestView from "./components/LatestView";
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
  const cameFromRandom = location.pathname.startsWith("/article") && location.state?.from === "/random";
  const isRandom = location.pathname.startsWith("/random") || cameFromRandom;
  const isDate = !isTags && !isRandom;
  return (
    <nav className="nav-toggle">
      依 <Link to="/date" className={isDate ? "active" : ""}>日期</Link>
      <span className="nav-toggle-sep">/</span>
      <Link to="/tags" className={isTags ? "active" : ""}>標籤</Link>
      <span className="nav-toggle-sep">/</span>
      <Link to="/random" className={isRandom ? "active" : ""}>隨機</Link> 瀏覽
    </nav>
  );
}

export default function App() {
  return (
    <HashRouter>
      <header>
        <h1 className="site-title">
          <Link to="/date">「C觀點」文章庫</Link>
        </h1>
        <NavToggle />
        <ThemeToggle />
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/date" replace />} />
          <Route path="/date" element={<DateView />} />
          <Route path="/tags" element={<TagListView />} />
          <Route path="/tag/:tag" element={<TagFilteredView />} />
          <Route path="/random" element={<RandomView />} />
          <Route path="/latest" element={<LatestView />} />
          <Route path="/article/:nid" element={<ArticleView />} />
        </Routes>
      </main>
    </HashRouter>
  );
}
