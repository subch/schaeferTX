import React, { useRef, useEffect, useState } from 'react'
import Papa from 'papaparse'
import { Chart, registerables } from 'chart.js'
import { evaluateWestgard } from '../westgard'
import { detectValueColumns, NON_VALUE_COLUMN } from '../dataUtils'
Chart.register(...registerables)

// One analyte's full Westgard evaluation: column picker, chart, summary,
// violations list, and per-analyte CSV export. Each loaded analyte gets its
// own instance so several can be reviewed side by side.
export default function WestgardAnalyteCard({ id, name, rows, columns, enabledRules, ruleInfo, onRemove }) {
  const canvasRef = useRef(null)
  const chartRef = useRef(null)
  const [selectedCol, setSelectedCol] = useState(() => {
    let col = columns.find(k => !NON_VALUE_COLUMN.test(k) && rows.some(r => typeof r[k] === 'number'))
    if (!col) col = columns.find(k => rows.some(r => typeof r[k] === 'number'))
    return col || columns[0]
  })
  const [summary, setSummary] = useState(null)

  useEffect(() => {
    return () => { if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null } }
  }, [])

  useEffect(() => {
    if (!selectedCol || rows.length === 0) { setSummary(null); return }
    const values = rows.map(r => Number(r[selectedCol])).filter(v => !Number.isNaN(v))
    const res = evaluateWestgard(values, { enabledRules })
    setSummary(res.summary)
    renderChart(values, res.points, res.summary)
  }, [rows, selectedCol, enabledRules])

  function renderChart(values, points, summary) {
    const labels = values.map((_, i) => i + 1)
    const pointBg = points.map(p => p.rules.some(r => r.severity === 'reject') ? 'rgba(255,82,82,1)' : p.rules.some(r => r.severity === 'warning') ? 'rgba(255,195,0,1)' : 'rgba(99,255,200,0.9)')

    const data = {
      labels,
      datasets: [{
        label: 'QC value',
        data: values,
        borderColor: 'rgba(111,184,255,0.9)',
        backgroundColor: 'rgba(111,184,255,0.12)',
        pointBackgroundColor: pointBg,
        tension: 0.2,
        pointRadius: 4,
      }],
    }

    const m = summary.mean
    const s = summary.computedSd
    const bands = [1, 2, 3]
    bands.forEach((k, idx) => {
      data.datasets.push({ label: `+${k}SD`, data: labels.map(() => m + k * s), pointRadius: 0, borderColor: idx === 0 ? 'rgba(93,212,184,0.25)' : 'rgba(111,184,255,0.18)', borderDash: [6, 4], tension: 0 })
      data.datasets.push({ label: `-${k}SD`, data: labels.map(() => m - k * s), pointRadius: 0, borderColor: idx === 0 ? 'rgba(93,212,184,0.25)' : 'rgba(111,184,255,0.18)', borderDash: [6, 4], tension: 0 })
    })

    const config = {
      type: 'line', data,
      options: {
        responsive: true, interaction: { mode: 'index', intersect: false },
        scales: { y: { beginAtZero: false } },
        plugins: { legend: { display: false }, title: { display: true, text: name, color: '#eef3f8', font: { size: 13, weight: '600' } } },
      },
    }

    if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null }
    chartRef.current = new Chart(canvasRef.current.getContext('2d'), config)
  }

  function exportAnnotated() {
    if (!rows || rows.length === 0 || !selectedCol) return
    const values = rows.map(r => Number(r[selectedCol])).filter(v => !Number.isNaN(v))
    const res = evaluateWestgard(values, { enabledRules })
    const annotated = rows.map((r, i) => ({ ...r, __qc_value: r[selectedCol], __violations: (res.points[i] && res.points[i].rules.map(x => x.name).join('|')) || '' }))
    const csv = Papa.unparse(annotated)
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `${name.replace(/\s+/g, '-').toLowerCase()}-annotated.csv`; a.click(); URL.revokeObjectURL(url)
  }

  return (
    <div className="card">
      <div className="demo-header" style={{ marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>{name}</h3>
        <button className="btn btn-ghost" onClick={() => onRemove(id)}>Remove</button>
      </div>

      <div className="field-row">
        <label className="hint" htmlFor={`col-select-${id}`}>Column:</label>
        <select id={`col-select-${id}`} value={selectedCol || ''} onChange={e => setSelectedCol(e.target.value)}>
          {columns.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button className="btn btn-ghost" onClick={exportAnnotated}>Export Annotated CSV</button>
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
            {Object.entries(summary.counts).length === 0 && <li>No violations detected <span className="badge none">clean</span></li>}
            {Object.entries(summary.counts).map(([rule, c]) => (
              <li key={rule} title={ruleInfo[rule]?.description}>
                <div>
                  <span className="rule-code">{rule}</span>
                  <span className="rule-desc">{ruleInfo[rule]?.short}</span>
                </div>
                <span className={`badge ${ruleInfo[rule]?.severity === 'warning' ? 'warning' : ''}`}>{c}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
