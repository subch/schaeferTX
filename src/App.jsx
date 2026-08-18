import React, { useEffect, useState } from 'react'
import { Routes, Route, Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import WestgardDemo from './components/WestgardDemo'
import LeveyJenningsDemo from './components/LeveyJenningsDemo'
import HL7Visualizer from './components/HL7Visualizer'

const NAV_ITEMS = [
  { path: '/', label: 'Home' },
  { path: '/projects', label: 'Projects' },
  { path: '/westgard', label: 'Westgard Demo' },
  { path: '/levey-jennings', label: 'Levey-Jennings Demo' },
  { path: '/hl7', label: 'HL7 Visualizer' },
  { path: '/about', label: 'About' },
]

const DEMOS = [
  {
    icon: '📉',
    title: 'Westgard rule explainer & demo',
    description: 'An interactive control-chart tool implementing the standard Westgard multi-rules, with CSV import/export and rule toggles for exploring assay QC data.',
    tags: ['React', 'Chart.js', 'QC analytics'],
    path: '/westgard',
  },
  {
    icon: '📈',
    title: 'Levey-Jennings chart demo',
    description: 'Multi-level Levey-Jennings charting with target mean/SD overrides and a monthly PDF report — chart snapshots, flagged points, and a review & approval page for lab director sign-off.',
    tags: ['React', 'Chart.js', 'PDF export'],
    path: '/levey-jennings',
  },
  {
    icon: '🩺',
    title: 'HL7 message visualizer',
    description: 'An interactive explainer for HL7 v2.x messages — click any field in an order, result, document, or acknowledgement message to see what it means, all parsed client-side.',
    tags: ['React', 'HL7 v2.x', 'Interop'],
    path: '/hl7',
  },
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

function DemoCard({ demo }) {
  return (
    <div className="card project-card">
      <div className="icon">{demo.icon}</div>
      <h3>{demo.title}</h3>
      <p>{demo.description}</p>
      <div className="tag-row">
        {demo.tags.map((tag) => <span className="tag" key={tag}>{tag}</span>)}
      </div>
      <div>
        <Link className="btn btn-ghost" to={demo.path}>Open demo →</Link>
      </div>
    </div>
  )
}

function HomePage() {
  return (
    <>
      <section className="hero container">
        <span className="eyebrow">Quality analytics &amp; applied statistics</span>
        <h1>Turning laboratory data into decisions you can trust.</h1>
        <p className="lead">
          I help labs and technical teams build reliable QC processes, clear visualizations,
          and reproducible statistical tools — from Westgard multi-rule evaluation to
          HL7 interop and custom analytics software.
        </p>
        <div className="hero-actions">
          <a className="btn btn-primary" href="#demos">Explore the demos</a>
          <Link className="btn btn-ghost" to="/contact">Get in touch</Link>
        </div>
        <div className="hero-stats">
          <div><strong>3</strong><span>Interactive demos</span></div>
          <div><strong>100%</strong><span>Client-side, no data upload</span></div>
          <div><strong>OSS</strong><span>Open source on GitHub</span></div>
        </div>
      </section>

      <section className="page-section container" id="demos">
        <div className="section-head">
          <span className="eyebrow">Try it yourself</span>
          <h2>Live demos</h2>
          <p>Each one is a standalone tool you can link to directly — no login, nothing uploaded.</p>
        </div>
        <div className="grid cols-3">
          {DEMOS.map((demo) => <DemoCard demo={demo} key={demo.path} />)}
        </div>
      </section>

      <section className="page-section tight container">
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
    </>
  )
}

function ProjectsPage() {
  return (
    <section className="page-section container">
      <div className="section-head">
        <span className="eyebrow">Selected work</span>
        <h2>Projects</h2>
        <p>A growing collection of tools built for laboratory quality control and data analysis.</p>
      </div>
      <div className="grid cols-2">
        {DEMOS.map((demo) => <DemoCard demo={demo} key={demo.path} />)}
      </div>
    </section>
  )
}

function WestgardPage() {
  return (
    <section className="page-section container">
      <div className="demo-header">
        <div>
          <span className="eyebrow">Interactive demo</span>
          <h2 style={{ margin: 0 }}>Westgard rule explainer &amp; demo</h2>
        </div>
        <Link className="btn btn-ghost" to="/projects">← All projects</Link>
      </div>
      <WestgardDemo />
    </section>
  )
}

function LeveyJenningsPage() {
  return (
    <section className="page-section container">
      <div className="demo-header">
        <div>
          <span className="eyebrow">Interactive demo</span>
          <h2 style={{ margin: 0 }}>Levey-Jennings chart demo</h2>
        </div>
        <Link className="btn btn-ghost" to="/projects">← All projects</Link>
      </div>
      <LeveyJenningsDemo />
    </section>
  )
}

function HL7Page() {
  return (
    <section className="page-section container">
      <div className="demo-header">
        <div>
          <span className="eyebrow">Interactive demo</span>
          <h2 style={{ margin: 0 }}>HL7 message visualizer</h2>
        </div>
        <Link className="btn btn-ghost" to="/projects">← All projects</Link>
      </div>
      <HL7Visualizer />
    </section>
  )
}

function AboutPage() {
  return (
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
  )
}

function ContactPage() {
  return (
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
  )
}

function NotFoundPage() {
  return (
    <section className="page-section container">
      <div className="section-head">
        <span className="eyebrow">404</span>
        <h2>Page not found</h2>
        <p>That page doesn't exist. <Link to="/">Back to home</Link>.</p>
      </div>
    </section>
  )
}

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    setMenuOpen(false)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [location.pathname])

  return (
    <div className="app">
      <a className="skip-link" href="#main-content">Skip to content</a>

      <header className="site-header">
        <div className="container">
          <button className="brand" onClick={() => navigate('/')} aria-label="Schaefer TX — home">
            <span className="brand-mark">S</span>
            <span>
              Schaefer TX
              <span className="brand-sub">Technical Scientific Consulting</span>
            </span>
          </button>

          <nav className={`main-nav${menuOpen ? ' open' : ''}`} aria-label="Primary">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
              >
                {item.label}
              </NavLink>
            ))}
            <Link className="nav-cta" to="/contact">Contact</Link>
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
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/westgard" element={<WestgardPage />} />
          <Route path="/levey-jennings" element={<LeveyJenningsPage />} />
          <Route path="/hl7" element={<HL7Page />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
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
