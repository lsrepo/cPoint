import { HashRouter, Routes, Route, Navigate, Link } from "react-router-dom";
import "./index.css";

function Placeholder() {
  return <p>此檢視尚未實作。</p>;
}

export default function App() {
  return (
    <HashRouter>
      <header>
        <h1 className="site-title">施永青「C觀點」文章庫</h1>
        <nav>
          <Link to="/date">依日期</Link>
          <Link to="/tags">依標籤</Link>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/date" replace />} />
          <Route path="/date" element={<Placeholder />} />
          <Route path="/tags" element={<Placeholder />} />
          <Route path="/tag/:tag" element={<Placeholder />} />
          <Route path="/article/:nid" element={<Placeholder />} />
        </Routes>
      </main>
    </HashRouter>
  );
}
