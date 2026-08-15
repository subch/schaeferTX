import React, { useState } from 'react'
import WestgardDemo from './components/WestgardDemo'

const NAV_ITEMS = [
  { id: 'home', label: 'Home' },
  { id: 'projects', label: 'Projects' },
  { id: 'westgard', label: 'Westgard Demo' },
  { id: 'about', label: 'About' },
]

const SERVICES = [
  {
    icon: '📊',
    title: 'Laboratory QC Analytics',
    body: 'Multi-rule QC evaluation, control chart design, and sigma-metric–based risk assessment for clinical and analytical labs.',
  },
  {
    icon: '📈',
    title: 'Data Visualization',
    body: 'Interactive dashboards and charts that make complex process and quality data legible to technical and non-technical audiences alike.',
  },
  {
    icon: '🧮',
    title: 'Applied Statistics',
    body: 'Robust estimators, reproducible analysis pipelines, and statistically sound methods for quality and process monitoring.',
  },
]

export default function App() {
  const [page, setPage] = useState('home')
  const [menuOpen, setMenuOpen] = useState(false)

  function goto(next) {
    setPage(next)
    setMenuOpen(false)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="app">
      <a className="skip-link" href="#main-content">Skip to content</a>

      <header className="site-header">
        <div className="container">
          <button className="brand" onClick={() => goto('home')} aria-label="Schaefer TX — home">
            <span className="brand-mark">S</span>
            <span>
              Schaefer TX
              <span className="brand-sub">Technical Scientific Consulting</span>
            </span>
          </button>

          <nav className={`main-nav${menuOpen ? ' open' : ''}`} aria-label="Primary">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                onClick={() => goto(item.id)}
                aria-current={page === item.id ? 'page' : undefined}
              >
                {item.label}
              </button>
            ))}
            <button className="nav-cta" onClick={() => goto('contact')}>Contact</button>
          </nav>

          <button
            className="menu-toggle"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
          >
            {menuOpen ? '✕' : '☰'}
          </button>
        </div>
      </header>

      <main className="content" id="main-content">
        {page === 'home' && (
          <>
            <section className="hero container">
              <span className="eyebrow">Quality analytics &amp; applied statistics</span>
              <h1>Turning laboratory data into decisions you can trust.</h1>
              <p className="lead">
                I help labs and technical teams build reliable QC processes, clear visualizations,
                and reproducible statistical tools — from Westgard multi-rule evaluation to
                custom analytics software.
              </p>
              <div className="hero-actions">
                <button className="btn btn-primary" onClick={() => goto('westgard')}>Try the Westgard demo</button>
                <button className="btn btn-ghost" onClick={() => goto('contact')}>Get in touch</button>
              </div>
              <div className="hero-stats">
                <div><strong>6</strong><span>Westgard rules implemented</span></div>
                <div><strong>100%</strong><span>Client-side, no data upload</span></div>
                <div><strong>OSS</strong><span>Open source on GitHub</span></div>
              </div>
            </section>

            <section className="page-section container">
              <div className="section-head">
                <span className="eyebrow">What I do</span>
                <h2>Services</h2>
              </div>
              <div className="grid cols-3">
                {SERVICES.map((s) => (
                  <div className="card" key={s.title}>
                    <div className="icon">{s.icon}</div>
                    <h3>{s.title}</h3>
                    <p>{s.body}</p>
                  </div>
                ))}
              </div>
            </section>

            <section className="page-section tight container">
              <div className="feature-banner">
                <div>
                  <span className="eyebrow">Featured project</span>
                  <h3>Westgard rule explainer &amp; demo</h3>
                  <p>
                    Upload a CSV of QC values and see 1_2s, 1_3s, 2_2s, R4s, 4_1s, and 10_x rules
                    evaluated live on an interactive control chart.
                  </p>
                </div>
                <button className="btn btn-primary" onClick={() => goto('westgard')}>Open demo →</button>
              </div>
            </section>
          </>
        )}

        {page === 'projects' && (
          <section className="page-section container">
            <div className="section-head">
              <span className="eyebrow">Selected work</span>
              <h2>Projects</h2>
              <p>A growing collection of tools built for laboratory quality control and data analysis.</p>
            </div>
            <div className="grid cols-2">
              <div className="card project-card">
                <div className="icon">📉</div>
                <h3>Westgard rule explainer &amp; demo</h3>
                <p>
                  An interactive control-chart tool implementing the standard Westgard multi-rules,
                  with CSV import/export and rule toggles for exploring assay QC data.
                </p>
                <div className="tag-row">
                  <span className="tag">React</span>
                  <span className="tag">Chart.js</span>
                  <span className="tag">QC analytics</span>
                </div>
                <div>
                  <button className="btn btn-ghost" onClick={() => goto('westgard')}>Open demo →</button>
                </div>
              </div>
            </div>
          </section>
        )}

        {page === 'westgard' && (
          <section className="page-section container">
            <div className="demo-header">
              <div>
                <span className="eyebrow">Interactive demo</span>
                <h2 style={{ margin: 0 }}>Westgard rule explainer &amp; demo</h2>
              </div>
              <button className="btn btn-ghost" onClick={() => goto('projects')}>← All projects</button>
            </div>
            <WestgardDemo />
          </section>
        )}

        {page === 'about' && (
          <section className="page-section container">
            <div className="about-grid">
              <div>
                <span className="eyebrow">About</span>
                <h2>Hi, I'm Schaefer.</h2>
                <p>
                  I'm a technical scientific consultant focusing on laboratory QC analytics, data
                  visualization, and reproducible software. I work with labs and technical teams to
                  turn raw process data into tools and visuals that support better decisions.
                </p>
                <p>
                  My projects are built to be transparent and reproducible — open source where
                  possible, with an emphasis on statistically sound methods over black-box results.
                </p>
              </div>
              <div className="card">
                <h3>Focus areas</h3>
                <ul className="about-list">
                  <li>Westgard multi-rule &amp; sigma-metric QC design</li>
                  <li>Control charting and process monitoring</li>
                  <li>Robust statistics (median/MAD, resistant estimators)</li>
                  <li>Interactive data visualization</li>
                  <li>Reproducible analysis pipelines</li>
                </ul>
              </div>
            </div>
          </section>
        )}

        {page === 'contact' && (
          <section className="page-section container">
            <div className="section-head">
              <span className="eyebrow">Get in touch</span>
              <h2>Contact</h2>
              <p>Have a QC analytics or data visualization project in mind? Reach out.</p>
            </div>
            <div className="card contact-card">
              <div className="contact-row">
                <span className="icon">✉️</span>
                <div>
                  <div>Email</div>
                  <a href="mailto:tschaefer0@gmail.com">tschaefer0@gmail.com</a>
                </div>
              </div>
              <div className="contact-row">
                <span className="icon">💻</span>
                <div>
                  <div>GitHub</div>
                  <a href="https://github.com/subch" target="_blank" rel="noreferrer">github.com/subch</a>
                </div>
              </div>
            </div>
          </section>
        )}
      </main>

      <footer className="site-footer">
        <div className="container">
          <small>© {new Date().getFullYear()} Schaefer TX</small>
          <div className="footer-links">
            <a href="https://github.com/subch/schaeferTX" target="_blank" rel="noreferrer">Source</a>
            <a href="mailto:tschaefer0@gmail.com">Email</a>
          </div>
        </div>
      </footer>
    </div>
  )
}
