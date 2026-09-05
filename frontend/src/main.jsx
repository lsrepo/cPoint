import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Registering a service worker is one of Chrome's requirements for the
// site to be installable as a desktop/home-screen app -- which in turn
// exempts it from the autoplay-needs-a-user-gesture restriction (see
// ArticleAudioPlayer.jsx). No caching happens here; see public/sw.js.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
  })
}
