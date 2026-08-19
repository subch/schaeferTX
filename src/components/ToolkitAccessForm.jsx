// Lead capture for the private toolkit.
//
// The public demos stay open — gating them would just annoy the exact people
// worth reaching. What's gated is access to the full suite (QC Workbench,
// Batch Review, Calibration, HL7 Workbench), which is where a lab director
// gets to try the real thing.
//
// Deliberately no Supabase SDK here: this is one INSERT, and the marketing
// site shouldn't gain ~120 KB of JavaScript for it. A plain fetch against
// PostgREST does the same job.
//
// The key below is publishable. The demo_leads table has an insert-only RLS
// policy and no select policy at all, so this key can add a lead and cannot
// read anybody else's back.

import React, { useState } from 'react'

const SUPABASE_URL =
  import.meta.env?.VITE_SUPABASE_URL || 'https://gitwwldcuczklsgeegct.supabase.co'
const SUPABASE_KEY =
  import.meta.env?.VITE_SUPABASE_PUBLISHABLE_KEY ||
  'sb_publishable_XwTaLxmGDa7d52lVMgpA8A_G3mzfUQl'

const ROLES = [
  'Lab director',
  'Lab manager / supervisor',
  'Technical consultant',
  'Medical technologist',
  'IT / interfaces',
  'Other',
]

export default function ToolkitAccessForm({ demo = 'general' }) {
  const [form, setForm] = useState({ email: '', name: '', lab_name: '', role: '' })
  const [state, setState] = useState('idle') // idle | sending | done | error
  const [error, setError] = useState(null)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setState('sending')
    setError(null)
    try {
      const res = await fetch(`${SUPABASE_URL}/rest/v1/demo_leads`, {
        method: 'POST',
        headers: {
          apikey: SUPABASE_KEY,
          Authorization: `Bearer ${SUPABASE_KEY}`,
          'Content-Type': 'application/json',
          Prefer: 'return=minimal',
        },
        body: JSON.stringify({ ...form, demo, source: 'schaefertx.com' }),
      })
      if (!res.ok) throw new Error(`Request failed (${res.status})`)
      setState('done')
    } catch (err) {
      setError(err.message || String(err))
      setState('error')
    }
  }

  if (state === 'done') {
    return (
      <div className="card toolkit-form">
        <h2>Thanks — I'll be in touch.</h2>
        <p>
          I'll reach out to set up access to the full toolkit and answer anything
          about how it would fit your lab's workflow. If it's easier, email me
          directly at <a href="mailto:tschaefer0@gmail.com">tschaefer0@gmail.com</a>.
        </p>
      </div>
    )
  }

  return (
    <div className="card toolkit-form">
      <h2>Try the full toolkit</h2>
      <p>
        The demos above are the public slice. The full suite adds an analyte
        registry with per-level targets and sigma metrics, LC-MS/MS batch review
        (ion ratios, ISTD recovery, carryover, curve trending), weighted
        calibration with LOD/LOQ, an HL7 PHI scrubber, and signed monthly QC
        report PDFs.
      </p>
      <p className="muted-note">
        Tell me a little about your lab and I'll set you up. No automated
        mailing list — this goes to me.
      </p>

      <form onSubmit={submit} className="toolkit-fields">
        <div className="field-row">
          <label>
            <span>Email</span>
            <input type="email" required value={form.email} onChange={set('email')}
                   placeholder="you@yourlab.com" />
          </label>
          <label>
            <span>Name</span>
            <input type="text" value={form.name} onChange={set('name')}
                   placeholder="Your name" />
          </label>
        </div>
        <div className="field-row">
          <label>
            <span>Lab</span>
            <input type="text" value={form.lab_name} onChange={set('lab_name')}
                   placeholder="Lab or organization" />
          </label>
          <label>
            <span>Role</span>
            <select value={form.role} onChange={set('role')}>
              <option value="">Select…</option>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
        </div>

        {state === 'error' && (
          <div className="form-error" role="alert">
            Couldn't send that ({error}). Email me directly at{' '}
            <a href="mailto:tschaefer0@gmail.com">tschaefer0@gmail.com</a>.
          </div>
        )}

        <button className="btn btn-primary" type="submit" disabled={state === 'sending'}>
          {state === 'sending' ? 'Sending…' : 'Request access'}
        </button>
      </form>
    </div>
  )
}
