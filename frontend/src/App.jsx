import { useEffect, useState } from "react";
import { HashRouter, Routes, Route, Navigate, Link } from "react-router-dom";
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

export default function App() {
  return (
    <HashRouter>
      <header>
        <div className="header-left">
          <h1 className="site-title">施永青「C觀點」文章庫</h1>
          <nav>
            <Link to="/date">依日期</Link>
            <Link to="/tags">依標籤</Link>
          </nav>
        </div>
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
