import React, { useEffect, useState } from 'react'
import ToolkitAccessForm from './components/ToolkitAccessForm'
import { Routes, Route, Link, NavLink, Navigate, useLocation, useNavigate } from 'react-router-dom'
import WestgardDemo from './components/WestgardDemo'
import LeveyJenningsDemo from './components/LeveyJenningsDemo'
import HL7Visualizer from './components/HL7Visualizer'

const NAV_ITEMS = [
  { path: '/', label: 'Home' },
  { path: '/services', label: 'Services' },
  { path: '/demos', label: 'Demos' },
  { path: '/about', label: 'About' },
]

const DEMOS = [
  {
    icon: '📉',
    title: 'Westgard rule evaluator',
    description: 'Load QC data (or your own CSV) and see multirule violations — 1-3s, 2-2s, R-4s, 4-1s, 10x — flagged point by point, with rule toggles and plain-language explanations.',
    evidence: 'The same evaluation engine I build into private QC review tools for labs.',
    tags: ['Westgard multirules', 'CSV import', 'QC analytics'],
    path: '/westgard',
  },
  {
    icon: '📈',
    title: 'Levey-Jennings charts + PDF QC report',
    description: 'Multi-level LJ charting with target mean/SD overrides and a monthly PDF report: chart snapshots, flagged points, and a review page laid out for director sign-off.',
    evidence: 'A working model of the monthly QC review packet I build for labs replacing manual chart review.',
    tags: ['Levey-Jennings', 'PDF reports', 'QC review'],
    path: '/levey-jennings',
  },
  {
    icon: '🔌',
    title: 'HL7 v2 message visualizer',
    description: 'Paste or pick an HL7 v2.x message — orders, results, documents, ACKs — and click any field to see what it means. Parsed entirely in your browser.',
    evidence: 'How I approach interface work: read the message, map every field, document the mapping.',
    tags: ['HL7 v2.x', 'LIS interfaces', 'Interoperability'],
    path: '/hl7',
  },
]

const SERVICES = [
  {
    icon: '🖥️',
    title: 'Custom laboratory software & dashboards',
    body: 'Purpose-built tools for your lab’s actual workflow: QC review applications, turnaround-time dashboards, result reporting portals, and utilities that replace spreadsheet workarounds.',
    detail: 'Off-the-shelf LIS modules rarely match how your lab actually reviews QC or tracks TAT. I build small, focused web applications around your data and your workflow — tools your techs can open in a browser and use without training.',
    deliverables: 'Typical deliverables: a deployed web application, source code, documentation, and a handoff walkthrough.',
  },
  {
    icon: '📊',
    title: 'QC program design & analytics',
    body: 'Westgard multirule selection, sigma-metric analysis, QC frequency, and a Levey-Jennings review workflow your staff will actually follow.',
    detail: 'Which rules to run, at what frequency, on which analytes — grounded in each assay’s measured sigma, not a one-size-fits-all default. I help you design the QC plan and the review process around it, from daily tech review to monthly director sign-off.',
    deliverables: 'Typical deliverables: per-analyte rule recommendations, sigma-metric worksheets, and a documented QC review procedure.',
  },
  {
    icon: '🔌',
    title: 'Interfacing & interoperability',
    body: 'HL7 v2 interfaces built and maintained in Mirth Connect: instrument-to-LIS connections, order/result mapping, and support through LIS migrations.',
    detail: 'Interfaces are where labs lose the most time when things go quiet or map wrong. I build and document Mirth Connect channels, map ORM/ORU segments field by field, and keep the mapping documents current so the next migration isn’t archaeology.',
    deliverables: 'Typical deliverables: working Mirth channels, field-level mapping documents, and test message sets.',
  },
  {
    icon: '📋',
    title: 'Compliance & inspection readiness',
    body: 'Support for your lab’s compliance program: SOP drafting and review, QC documentation cleanup, and preparation ahead of CAP and CLIA inspections.',
    detail: 'I work alongside your laboratory director and quality staff — reviewing SOPs against checklist requirements, closing documentation gaps, and doing pre-inspection walkthroughs — so findings surface before the inspector does. Your director retains oversight; I make the paperwork defensible.',
    deliverables: 'Typical deliverables: gap analysis, revised SOPs, QC documentation templates, and a readiness punch list.',
  },
  {
    icon: '🧪',
    title: 'LC-MS/MS & toxicology consultation',
    body: 'Urine toxicology by LC-MS/MS is my home turf: method validation support, cutoff and confirmation strategy, troubleshooting, and data review.',
    detail: 'Screening cutoffs, confirmation panels, carryover, ion ratios, matrix effects, calibration drift — the details that decide whether a tox result stands up. I support validations, review data, and help troubleshoot when results stop making sense.',
    deliverables: 'Typical deliverables: validation protocol input, data review summaries, and written troubleshooting findings.',
  },
  {
    icon: '🧮',
    title: 'Scientific & statistical consultation',
    body: 'Method comparison, reference interval studies, measurement uncertainty, and ad-hoc analysis when a question needs a defensible statistical answer.',
    detail: 'Deming and Passing-Bablok regression, bias estimation, reference interval verification, uncertainty budgets — done with methods you can cite and scripts you can rerun. Useful for validations, inspection responses, and one-off questions.',
    deliverables: 'Typical deliverables: analysis report with methods cited, figures, and the reproducible analysis scripts.',
  },
]

const STEPS = [
  {
    n: '1',
    title: 'Scoping call',
    body: 'A short call about your lab, instruments, LIS, and the problem. No charge, no obligation — sometimes the answer is "you don’t need a consultant for this."',
  },
  {
    n: '2',
    title: 'Fixed-scope proposal',
    body: 'A written proposal with concrete deliverables, timeline, and price. You know what you’re getting before any work starts.',
  },
  {
    n: '3',
    title: 'Build & deliver',
    body: 'I do the work, keep you updated, and hand off with documentation — source code, mapping documents, or written findings you keep either way.',
  },
]

function DemoCard({ demo }) {
  return (
    <div className="card project-card">
      <div className="icon" aria-hidden="true">{demo.icon}</div>
      <h3>{demo.title}</h3>
      <p>{demo.description}</p>
      <p className="demo-evidence">{demo.evidence}</p>
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
        <span className="eyebrow">Schaefer TX Consulting</span>
        <h1>Custom software and QC expertise for clinical and toxicology labs.</h1>
        <p className="lead">
          I build lab software — QC review tools, dashboards, HL7/LIS interfaces — and
          consult on QC program design and compliance for clinical and toxicology
          laboratories. My background is urine toxicology by LC-MS/MS, so I speak both
          languages: the bench and the code.
        </p>
        <div className="hero-actions">
          <Link className="btn btn-primary" to="/demos">See the live demos</Link>
          <a className="btn btn-ghost" href="mailto:tschaefer0@gmail.com?subject=Scoping%20call%20request">Book a scoping call</a>
        </div>
        <div className="hero-stats">
          <div><strong>3</strong><span>Live demos, no login</span></div>
          <div><strong>100%</strong><span>Client-side — your data never leaves your browser</span></div>
          <div><strong>OSS</strong><span>Source on GitHub</span></div>
        </div>
      </section>

      <section className="page-section tight container">
        <div className="audience-strip card">
          <span className="eyebrow">Who I work with</span>
          <p className="audience-text">
            Lab directors, lab managers, and CLIA technical consultants at clinical and
            toxicology laboratories — especially urine toxicology labs running LC-MS/MS —
            who need software, QC, or interface work done by someone who already knows
            what a Levey-Jennings chart and an ORU message are.
          </p>
        </div>
      </section>

      <section className="page-section tight container">
        <div className="section-head">
          <span className="eyebrow">What I do</span>
          <h2>Services</h2>
          <p>Six ways I help labs, from custom software to inspection prep.</p>
        </div>
        <div className="grid cols-3">
          {SERVICES.slice(0, 3).map((s) => (
            <div className="card" key={s.title}>
              <div className="icon" aria-hidden="true">{s.icon}</div>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </div>
          ))}
        </div>
        <div className="section-more">
          <Link className="btn btn-ghost" to="/services">All six services →</Link>
        </div>
      </section>

      <section className="page-section container" id="demos">
        <div className="section-head">
          <span className="eyebrow">Proof, not promises</span>
          <h2>Live demos</h2>
          <p>
            Working tools, not screenshots. Each runs entirely in your browser — load the
            sample data or your own CSV; nothing is uploaded anywhere.
          </p>
        </div>
        <div className="grid cols-3">
          {DEMOS.map((demo) => <DemoCard demo={demo} key={demo.path} />)}
        </div>
      </section>

      <section className="page-section tight container">
        <div className="section-head">
          <span className="eyebrow">How it works</span>
          <h2>Engagements in three steps</h2>
        </div>
        <div className="grid cols-3">
          {STEPS.map((step) => (
            <div className="card step-card" key={step.n}>
              <div className="step-num" aria-hidden="true">{step.n}</div>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="page-section tight container">
        <div className="cta-band">
          <div>
            <h2>Have a lab problem that needs software, QC, or interface work?</h2>
            <p>Tell me about your lab and I’ll tell you honestly whether I can help.</p>
          </div>
          <a className="btn btn-primary" href="mailto:tschaefer0@gmail.com?subject=Scoping%20call%20request">Book a scoping call</a>
        </div>
      </section>
    </>
  )
}

function ServicesPage() {
  return (
    <section className="page-section container">
      <div className="section-head">
        <span className="eyebrow">Services</span>
        <h1>What I do for labs</h1>
        <p>
          Every engagement is fixed-scope with named deliverables — you’ll know what
          you’re getting and what it costs before work starts.
        </p>
      </div>
      <div className="service-list">
        {SERVICES.map((s) => (
          <div className="card service-detail" key={s.title}>
            <div className="icon" aria-hidden="true">{s.icon}</div>
            <div>
              <h3>{s.title}</h3>
              <p>{s.detail}</p>
              <p className="deliverables">{s.deliverables}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="section-more">
        <a className="btn btn-primary" href="mailto:tschaefer0@gmail.com?subject=Scoping%20call%20request">Book a scoping call</a>
        <Link className="btn btn-ghost" to="/demos">See the live demos</Link>
      </div>
    </section>
  )
}

function DemosPage() {
  return (
    <section className="page-section container">
      <div className="section-head">
        <span className="eyebrow">Live demos</span>
        <h1>Try the tools</h1>
        <p>
          These are working examples of the kind of software I build for labs — QC
          evaluation, chart review, and interface work. Everything runs in your browser;
          load the sample data or your own CSV, and nothing is uploaded anywhere.
        </p>
      </div>
      <div className="grid cols-2">
        {DEMOS.map((demo) => <DemoCard demo={demo} key={demo.path} />)}
      </div>
      <div className="mt">
        <ToolkitAccessForm demo="demos-page" />
      </div>
    </section>
  )
}

function WestgardPage() {
  return (
    <section className="page-section container">
      <div className="demo-header">
        <div>
          <span className="eyebrow">Live demo</span>
          <h1 style={{ margin: 0 }}>Westgard rule evaluator</h1>
        </div>
        <Link className="btn btn-ghost" to="/demos">← All demos</Link>
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
          <span className="eyebrow">Live demo</span>
          <h1 style={{ margin: 0 }}>Levey-Jennings charts + PDF QC report</h1>
        </div>
        <Link className="btn btn-ghost" to="/demos">← All demos</Link>
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
          <span className="eyebrow">Live demo</span>
          <h1 style={{ margin: 0 }}>HL7 v2 message visualizer</h1>
        </div>
        <Link className="btn btn-ghost" to="/demos">← All demos</Link>
      </div>
      <HL7Visualizer />
    </section>
  )
}

function AboutPage() {
  return (
    <section className="page-section container">
      <div className="about-grid">
        <div className="prose">
          <span className="eyebrow">About</span>
          <h1>Hi, I’m Travis Schaefer.</h1>
          <p>
            I’m a consultant for clinical and toxicology laboratories. My background is
            urine toxicology by LC-MS/MS
            {/* TODO(Travis): add years of experience and role(s), e.g. "— [X] years running
                confirmation testing as [role] at [lab type]" */}
            , and along the way I ended up building the software my labs needed but
            couldn’t buy: QC review tools, Levey-Jennings reporting, and HL7 interfaces
            in Mirth Connect.
          </p>
          <p>
            That combination is the point. Most developers have never watched a QC lot
            change go sideways, and most lab scientists don’t write production software.
            I do both, so labs get tools built by someone who understands why an R-4s flag
            matters and what an inspector will ask about it.
          </p>
          <p>
            Everything on this site runs client-side and the source is on GitHub — the
            same transparency I aim for in client work: documented methods, reproducible
            analysis, no black boxes.
          </p>
          {/* TODO(Travis): add credentials if applicable — degree(s), certifications
              (e.g. ASCP, NRCC), notable employers or lab settings. Do not publish
              anything here until confirmed accurate. */}
        </div>
        <div className="card">
          <h3>Deepest expertise</h3>
          <ul className="about-list">
            <li>Urine toxicology by LC-MS/MS — validation, cutoffs, data review</li>
            <li>Westgard multirule &amp; sigma-metric QC design</li>
            <li>Levey-Jennings review workflows and QC reporting</li>
            <li>HL7 v2 interfaces &amp; Mirth Connect</li>
            <li>Custom lab software (React, data pipelines, PDF reporting)</li>
            <li>Method comparison &amp; applied statistics</li>
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
        <h1>Contact</h1>
        <p>
          Email is best. A line or two about your lab type, instruments, LIS, and the
          problem you’re trying to solve is plenty to start — I’ll get back to you to
          set up a scoping call.
          {/* TODO(Travis): add a concrete response-time commitment once you know what
              you can reliably hold to, e.g. "within one business day". Deliberately
              omitted rather than promising a number that was never confirmed. */}
        </p>
      </div>
      <div className="card contact-card">
        <div className="contact-row">
          <span className="icon" aria-hidden="true">✉️</span>
          <div>
            <div>Email</div>
            <a href="mailto:tschaefer0@gmail.com">tschaefer0@gmail.com</a>
          </div>
        </div>
        <div className="contact-row">
          <span className="icon" aria-hidden="true">💻</span>
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
        <h1>Page not found</h1>
        <p>That page doesn’t exist. <Link to="/">Back to home</Link>.</p>
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
              <span className="brand-sub">Clinical &amp; Toxicology Lab Consulting</span>
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
          <Route path="/services" element={<ServicesPage />} />
          <Route path="/demos" element={<DemosPage />} />
          <Route path="/projects" element={<Navigate to="/demos" replace />} />
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
          <small>© {new Date().getFullYear()} Schaefer TX — Consulting for clinical &amp; toxicology laboratories</small>
          <div className="footer-links">
            <a href="https://github.com/subch/schaeferTX" target="_blank" rel="noreferrer">Source</a>
            <a href="mailto:tschaefer0@gmail.com">Email</a>
          </div>
        </div>
      </footer>
    </div>
  )
}
