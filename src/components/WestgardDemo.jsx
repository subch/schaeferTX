import React, {useRef, useEffect, useState} from 'react'
import Papa from 'papaparse'
import { Chart, registerables } from 'chart.js'
import { mean, sd, evaluateWestgard } from '../westgard'
Chart.register(...registerables)

// Columns that look like a row index/timestamp rather than QC data, so the
// column auto-picker skips them in favor of an actual measured value.
const NON_VALUE_COLUMN = /^(time|date|index|idx|id|sample|run|seq|point|obs)$/i

const EXAMPLES = [
  { key: 'sodium', label: 'Sodium (Na+)', file: 'sodium.csv', hint: 'electrolyte spikes → 1_2s, 2_2s' },
  { key: 'potassium', label: 'Potassium (K+)', file: 'potassium.csv', hint: 'reagent drift → 4_1s, 10_x' },
  { key: 'lipids', label: 'Lipids (Cholesterol)', file: 'lipids.csv', hint: 'systematic shift → 10_x' },
  { key: 'glucose', label: 'Glucose', file: 'glucose.csv', hint: 'in control → no violations' },
  { key: 'calcium', label: 'Calcium', file: 'calcium.csv', hint: 'single outlier → 1_3s' },
]

export default function WestgardDemo(){
  const canvasRef = useRef(null)
  const chartRef = useRef(null)
  const [summary, setSummary] = useState(null)
  const [columns, setColumns] = useState([])
  const [selectedCol, setSelectedCol] = useState(null)
  const [rows, setRows] = useState([])
  const [enabledRules, setEnabledRules] = useState({ '1_2s': true, '1_3s': true, '2_2s': true, 'R4s': true, '4_1s': true, '10_x': true })
  const [loadError, setLoadError] = useState(null)

  useEffect(()=>{
    return ()=>{
      if (chartRef.current){
        chartRef.current.destroy()
        chartRef.current = null
      }
    }
  },[])

  // Re-run analysis whenever the parsed data, chosen column, or rule set changes.
  useEffect(()=>{
    if (!selectedCol || rows.length === 0){ setSummary(null); return }
    const values = rows.map(r=>Number(r[selectedCol])).filter(v=>!Number.isNaN(v))
    const res = evaluateWestgard(values, { enabledRules })
    setSummary(res.summary)
    renderChart(values, res.points, res.summary)
  }, [rows, selectedCol, enabledRules])

  function onFile(file){
    setLoadError(null)
    Papa.parse(file, { header: true, dynamicTyping: true, skipEmptyLines: true, comments: '#', complete: ({data, meta})=>{
      if (!data || data.length === 0){ alert('No rows parsed'); return }
      setRows(data)
      const keys = Object.keys(data[0])
      setColumns(keys)
      // Prefer a numeric column that isn't a time/index/id column; fall back to any numeric column.
      let col = keys.find(k=> !NON_VALUE_COLUMN.test(k) && data.some(r=> typeof r[k] === 'number'))
      if (!col) col = keys.find(k=> data.some(r=> typeof r[k] === 'number'))
      setSelectedCol(col || keys[0])
    }})
  }

  function loadExample(file){
    setLoadError(null)
    fetch(`/examples/${file}`)
      .then(r=>{ if (!r.ok) throw new Error(`${file} (${r.status})`); return r.text() })
      .then(t=> onFile(new File([t], file, {type:'text/csv'})))
      .catch(err=> setLoadError(`Could not load example: ${err.message}`))
  }

  function renderChart(values, points, summary){
    const labels = values.map((_,i)=>i+1)
    const pointBg = points.map(p=> p.rules.some(r=> r.severity==='reject') ? 'rgba(255,82,82,1)' : p.rules.some(r=> r.severity==='warning') ? 'rgba(255,195,0,1)' : 'rgba(99,255,200,0.9)')

    const data = {
      labels,
      datasets: [{
        label: 'QC value',
        data: values,
        borderColor: 'rgba(111,184,255,0.9)',
        backgroundColor: 'rgba(111,184,255,0.12)',
        pointBackgroundColor: pointBg,
        tension: 0.2,
        pointRadius: 4
      }]
    }

    // add sd bands
    const m = summary.mean
    const s = summary.computedSd
    const bands = [1,2,3]

    bands.forEach((k, idx)=>{
      data.datasets.push({ label:`+${k}SD`, data: labels.map(()=> m + k*s), pointRadius:0, borderColor: idx===0 ? 'rgba(93,212,184,0.25)' : 'rgba(111,184,255,0.18)', borderDash:[6,4], tension:0 })
      data.datasets.push({ label:`-${k}SD`, data: labels.map(()=> m - k*s), pointRadius:0, borderColor: idx===0 ? 'rgba(93,212,184,0.25)' : 'rgba(111,184,255,0.18)', borderDash:[6,4], tension:0 })
    })

    const config = { type:'line', data, options:{ responsive:true, interaction:{mode:'index',intersect:false}, scales:{ y:{ beginAtZero:false }}, plugins:{ legend:{ display:false } } } }

    if (chartRef.current){ chartRef.current.destroy(); chartRef.current = null }
    chartRef.current = new Chart(canvasRef.current.getContext('2d'), config)
    chartRef.current.update()
  }

  function toggleRule(rule){ setEnabledRules(prev=> ({...prev, [rule]: !prev[rule]})) }

  function exportAnnotated(){
    if (!rows || rows.length===0 || !selectedCol) return
    const values = rows.map(r=>Number(r[selectedCol])).filter(v=>!Number.isNaN(v))
    const res = evaluateWestgard(values, { enabledRules })
    const annotated = rows.map((r,i)=> ({...r, __qc_value: r[selectedCol], __violations: (res.points[i] && res.points[i].rules.map(x=>x.name).join('|'))||'' }))
    const csv = Papa.unparse(annotated)
    const blob = new Blob([csv], {type:'text/csv'})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'annotated.csv'; a.click(); URL.revokeObjectURL(url)
  }

  return (
    <div>
      <div className="card">
        <div className="westgard-controls">
          <input type="file" accept=".csv,text/csv" onChange={e=> e.target.files[0] && onFile(e.target.files[0])} />
          <span className="hint">Upload a CSV with a numeric column (header OK). A likely value column will be suggested.</span>
        </div>

        <div className="westgard-controls">
          <span className="hint">Or load a dummy dataset:</span>
          {EXAMPLES.map(ex=> (
            <button key={ex.key} className="btn btn-ghost" title={ex.hint} onClick={()=>loadExample(ex.file)}>
              {ex.label}
            </button>
          ))}
        </div>

        {loadError && <p className="hint" role="alert">{loadError}</p>}

        {columns.length>0 && (
          <div className="field-row">
            <label className="hint" htmlFor="col-select">Column:</label>
            <select id="col-select" value={selectedCol||''} onChange={e=> setSelectedCol(e.target.value)}>
              {columns.map(c=> <option key={c} value={c}>{c}</option>)}
            </select>
            <button className="btn btn-ghost" onClick={exportAnnotated}>Export Annotated CSV</button>
          </div>
        )}

        <div className="rules-row">
          {Object.keys(enabledRules).map(r=> (
            <label key={r} className="rule-toggle">
              <input type="checkbox" checked={enabledRules[r]} onChange={()=>toggleRule(r)} /> {r}
            </label>
          ))}
        </div>

        <div className="chart-wrap">
          <canvas ref={canvasRef} />
        </div>

        {summary && (
          <div>
            <div className="summary-grid">
              <div className="stat-tile"><strong>{summary.n}</strong><span>Count</span></div>
              <div className="stat-tile"><strong>{Number(summary.mean).toFixed(3)}</strong><span>Mean</span></div>
              <div className="stat-tile"><strong>{Number(summary.sd).toFixed(3)}</strong><span>SD</span></div>
            </div>
            <ul className="violations-list">
              {Object.entries(summary.counts).length===0 && <li>No violations detected <span className="badge none">clean</span></li>}
              {Object.entries(summary.counts).map(([rule,c])=> (
                <li key={rule}>{rule} <span className="badge">{c}</span></li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="card">
        <h3>Notes and references</h3>
        <p>This implementation follows the standard Westgard multi-rules (1_2s (warning), 1_3s, 2_2s, R4s, 4_1s, 10_x). For more background and the classical descriptions see <a href="https://www.westgard.com/westgard-rules.html" target="_blank" rel="noreferrer">westgard.com</a>.</p>
      </div>

      <div className="card">
        <h3>Paper summary — PMC9300779</h3>
        <p>Below is a concise, site-ready summary of key points from the literature (PMC9300779) that are relevant to Westgard multi-rule QC practice. This wording paraphrases the paper and highlights actionable implications for laboratory QC.</p>
        <ul>
          <li><strong>Variable performance of Westgard rules:</strong> Westgard multi-rules are effective for detecting many analytical errors, but their sensitivity and specificity depend on assay characteristics (imprecision, bias, and sigma performance); highly sensitive rules can increase false positives.</li>
          <li><strong>Control limits and estimators:</strong> The choice between short-term (sample) mean/SD and long-term or target values significantly affects rule performance; robust estimators (median/MAD) or user-supplied targets can reduce the influence of transient outliers and better reflect true process variation.</li>
          <li><strong>Risk-based QC and sigma metrics:</strong> Combining Westgard rules with sigma-metric–based risk assessment improves decision-making: high-sigma assays can use simpler rules while low-sigma assays require stricter monitoring or corrective action thresholds.</li>
          <li><strong>Sequence-based rule considerations:</strong> Rules that rely on consecutive points (e.g., 4_1s, 10_x, 2_2s, R4s) need adequate run length to be meaningful and are sensitive to autocorrelation; retrospective analysis or simulation can validate chosen rules against real assay data.</li>
          <li><strong>Practical recommendations:</strong> Tailor rule sets to each assay, use robust or long-term estimates when appropriate, visualize rule context (bands and side-of-mean) for interpretation, and periodically re-evaluate QC strategies, especially after method changes.</li>
        </ul>
        <p>Reference: <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC9300779/" target="_blank" rel="noreferrer">PMC9300779</a></p>
      </div>
    </div>
  )
}
