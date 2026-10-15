import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App.tsx'
import './index.css'

// Scroll-reveal styles apply only when this script runs (see index.css).
document.documentElement.classList.add('js')

const root = document.getElementById('root')
// index.html always has #root; without it there is nothing to render into.
if (!root) throw new Error('Missing #root element')

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
