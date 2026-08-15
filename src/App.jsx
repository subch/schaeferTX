import React, {useState} from 'react'
import WestgardDemo from './components/WestgardDemo'

export default function App(){
  const [page, setPage] = useState('home')
  return (
    <div className="app">
      <header className="site-header">
        <h1 className="brand">Schaefer TX</h1>
        <nav>
          <button onClick={()=>setPage('home')}>Home</button>
          <button onClick={()=>setPage('projects')}>Projects</button>
          <button onClick={()=>setPage('westgard')}>Westgard Demo</button>
          <button onClick={()=>setPage('about')}>About</button>
        </nav>
      </header>

      <main className="content">
        {page === 'home' && (
          <section>
            <h2>Technical Scientific Consulting</h2>
            <p>Services in laboratory quality analytics, data visualization, and applied statistics.</p>
            <p>Explore projects and interactive demos.</p>
          </section>
        )}

        {page === 'projects' && (
          <section>
            <h2>Projects</h2>
            <ul>
              <li><button onClick={()=>setPage('westgard')}>Westgard rule explainer & demo</button></li>
            </ul>
          </section>
        )}

        {page === 'westgard' && (
          <WestgardDemo />
        )}

        {page === 'about' && (
          <section>
            <h2>About</h2>
            <p>Hi — I'm a technical scientific consultant focusing on QC analytics, visualization, and reproducible software.</p>
          </section>
        )}
      </main>

      <footer className="site-footer">
        <small>© {new Date().getFullYear()} Schaefer TX</small>
      </footer>
    </div>
  )
}
