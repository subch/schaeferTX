import React, {useRef, useEffect, useState} from 'react'
import Papa from 'papaparse'
import { Chart, registerables } from 'chart.js'
import { mean, sd, evaluateWestgard } from '../westgard'
import { detectValueColumns, NON_VALUE_COLUMN } from '../dataUtils'
import DataTemplateCard from './DataTemplateCard'
Chart.register(...registerables)

const TEMPLATE_COLUMNS = [
  { key: 'Time', label: 'Time', type: 'index', desc: 'Row order / run number. Any column named Time, Date, Index, ID, Sample, Run, Seq, Point, or Obs is auto-detected and excluded from the value picker.' },
  { key: 'Value', label: 'Value', type: 'numeric', desc: 'The QC result for that run. The first numeric column that isn’t an index column is auto-selected, and any other column can be picked from the dropdown once loaded.' },
]
const TEMPLATE_ROWS = [
  { Time: 1, Value: 95 },
  { Time: 2, Value: 97 },
  { Time: 3, Value: 94 },
]

const EXAMPLES = [
  { key: 'sodium', label: 'Sodium (Na+)', file: 'sodium.csv', hint: 'electrolyte spikes → 1_2s, 2_2s' },
  { key: 'potassium', label: 'Potassium (K+)', file: 'potassium.csv', hint: 'reagent drift → 4_1s, 10_x' },
  { key: 'lipids', label: 'Lipids (Cholesterol)', file: 'lipids.csv', hint: 'systematic shift → 10_x' },
  { key: 'glucose', label: 'Glucose', file: 'glucose.csv', hint: 'in control → no violations' },
  { key: 'calcium', label: 'Calcium', file: 'calcium.csv', hint: 'single outlier → 1_3s' },
]

// What each rule flags and why it matters, shown as tooltips on the toggles
// and as inline explanations wherever a violation is reported.
const RULE_INFO = {
  '1_2s': { severity: 'warning', short: 'one point beyond 2 SD', description: 'A single control result falls beyond the mean ± 2 SD. Common in an in-control run by chance alone, so it’s treated as a warning to check the stricter rules below rather than an automatic reject.' },
  '1_3s': { severity: 'reject', short: 'one point beyond 3 SD', description: 'A single control result falls beyond the mean ± 3 SD — a clear outlier, usually from a random error (e.g. a sample mix-up or instrument glitch). Reject the run.' },
  '2_2s': { severity: 'reject', short: 'two points beyond 2 SD, same side', description: 'Two consecutive control results both exceed the mean ± 2 SD on the same side. Suggests a systematic error, such as a calibration or reagent shift. Reject the run.' },
  'R4s': { severity: 'reject', short: 'consecutive points spanning 4 SD', description: 'One control result exceeds +2 SD while the next (or previous) exceeds −2 SD — a swing of 4 SD between two points. Flags a sudden increase in random error. Reject the run.' },
  '4_1s': { severity: 'reject', short: 'four points beyond 1 SD, same side', description: 'Four consecutive control results all fall beyond 1 SD on the same side of the mean. Indicates a developing systematic shift. Reject the run.' },
  '10_x': { severity: 'reject', short: 'ten points on the same side', description: 'Ten consecutive control results fall on the same side of the mean, regardless of magnitude. Signals a persistent bias, such as a reagent lot change or calibration drift. Reject the run.' },
}

export default function WestgardDemo({ onNavigate }){
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
            <label key={r} className="rule-toggle" title={RULE_INFO[r].description}>
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
                <li key={rule} title={RULE_INFO[rule]?.description}>
                  <div>
                    <span className="rule-code">{rule}</span>
                    <span className="rule-desc">{RULE_INFO[rule]?.short}</span>
                  </div>
                  <span className={`badge ${RULE_INFO[rule]?.severity==='warning' ? 'warning' : ''}`}>{c}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="card">
        <h3>What are Westgard rules?</h3>
        <p>Westgard multi-rules are a set of statistical checks applied to laboratory quality-control (QC) results before a batch of patient results is released. Each rule looks for a different pattern in the QC data relative to its established mean and standard deviation (SD) — a single extreme value, a run drifting to one side, and so on. A <span className="severity-pill warning">warning</span> hit means "worth a second look"; a <span className="severity-pill reject">reject</span> hit means the run likely has a real analytical error and shouldn't be released until it's investigated.</p>

        <div className="rule-info-grid">
          {Object.entries(RULE_INFO).map(([code, info])=> (
            <div key={code} className="rule-info-card">
              <div>
                <span className="rule-code">{code}</span>
                <span className={`severity-pill ${info.severity}`}>{info.severity}</span>
              </div>
              <p>{info.description}</p>
            </div>
          ))}
        </div>

        <p>
          For the classical descriptions and background, see <a href="https://www.westgard.com/westgard-rules.html" target="_blank" rel="noreferrer">westgard.com</a>.
          These rules are applied on top of a Levey-Jennings chart — the mean/SD run chart itself — see the{' '}
          {onNavigate
            ? <a href="#" onClick={e => { e.preventDefault(); onNavigate('levey-jennings') }}>Levey-Jennings demo</a>
            : <span>Levey-Jennings demo</span>} for a monthly, multi-level view with a PDF export.
        </p>
      </div>

      <DataTemplateCard
        title="Input data template"
        description="Any CSV with a numeric result column works. Shape it like this — one row per run, in order:"
        columns={TEMPLATE_COLUMNS}
        sampleRows={TEMPLATE_ROWS}
        downloadFileName="westgard-template.csv"
      />

      <div className="card">
        <h3>Paper summary — PMC9300779</h3>
        <p>Rule performance isn't one-size-fits-all: sensitivity and specificity vary with each assay's imprecision, bias, and sigma-metric performance, so a rule set tuned for one analyte can create excess false alarms for another. The recommended approach is to match rule sensitivity to an assay's sigma performance, prefer long-term or robust (median/MAD) control limits over short-term sample statistics when available, and pair multi-rule QC with sigma-metric, risk-based decision-making to balance error detection against false positives.</p>
        <p>Reference: <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC9300779/" target="_blank" rel="noreferrer">PMC9300779</a></p>
      </div>
    </div>
  )
}
