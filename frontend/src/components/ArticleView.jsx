import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { getArticle } from "../api";
import { nextParagraphIndex } from "../scrollNav";
import CantoneseAudioPlayer from "./CantoneseAudioPlayer";

export default function ArticleView() {
  const { nid } = useParams();
  const location = useLocation();
  const backTo = location.state?.from || "/date";
  const isRandomMode = backTo === "/random";
  const [article, setArticle] = useState(undefined);
  const [error, setError] = useState(null);
  const paragraphRefs = useRef([]);

  useEffect(() => {
    setArticle(undefined);
    setError(null);
    getArticle(nid).then(setArticle).catch((err) => setError(err.message));
  }, [nid]);

  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key !== "ArrowDown") return;
      const paragraphs = paragraphRefs.current;
      const i = nextParagraphIndex(paragraphs.map((p) => p.getBoundingClientRect().top));
      if (i === -1) return;
      e.preventDefault();
      paragraphs[i].scrollIntoView({ behavior: "smooth", block: "start" });
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [article]);

  if (error) return <p>載入失敗，請稍後再試。</p>;
  if (article === undefined) return <p>載入中...</p>;
  if (article === null) return <p>找不到文章。</p>;

  paragraphRefs.current = [];

  return (
    <>
      <p><Link to={backTo}>&laquo; 返回文章列表</Link></p>
      <h1>{article.title}</h1>
      <p className="meta">
        {article.date} ·{" "}
        <a href={article.url} target="_blank" rel="noopener noreferrer">原文連結</a>
      </p>
      <p className="tags">
        {article.hashtags.map((t) => (
          <Link key={t} className="tag" to={`/tag/${encodeURIComponent(t)}`}>{t}</Link>
        ))}
      </p>
      <CantoneseAudioPlayer body={article.body} />
      <div className="article-body">
        {article.body.split("\n\n").map((para, i) => (
          <p key={i} ref={(el) => { paragraphRefs.current[i] = el; }}>{para}</p>
        ))}
      </div>
      <nav className="article-nav">
        {isRandomMode ? (
          <Link className="article-nav-prev" to="/random">&laquo; 隨機</Link>
        ) : article.prev ? (
          <Link className="article-nav-prev" to={`/article/${article.prev.nid}`} state={{ from: backTo }}>
            &laquo; {article.prev.date}
          </Link>
        ) : <span />}
        {isRandomMode ? (
          <Link className="article-nav-next" to="/random">隨機 &raquo;</Link>
        ) : article.next ? (
          <Link className="article-nav-next" to={`/article/${article.next.nid}`} state={{ from: backTo }}>
            {article.next.date} &raquo;
          </Link>
        ) : <span />}
      </nav>
    </>
  );
}
