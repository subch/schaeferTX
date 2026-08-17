import React, { useRef, useState, useMemo } from 'react'
import Papa from 'papaparse'
import { mean, sd } from '../westgard'
import { detectValueColumns, detectLabelColumn } from '../dataUtils'
import LevelChart from './LevelChart'
import DataTemplateCard from './DataTemplateCard'

const EXAMPLES = [
  { key: 'glucose', label: 'Glucose (2 levels)', file: 'lj-glucose.csv', hint: 'stable, in-control month' },
  { key: 'electrolytes', label: 'Sodium (2 levels)', file: 'lj-electrolytes.csv', hint: 'Level 2 drifting upward' },
  { key: 'lipids', label: 'Cholesterol (2 levels)', file: 'lj-lipids.csv', hint: 'Level 1 single outlier' },
]

const TEMPLATE_COLUMNS = [
  { key: 'Date', label: 'Date', type: 'date/index', desc: 'One run per row, in order. A Date/Time/Run/Index column is auto-detected and used for the x-axis, or omitted for a plain run number.' },
  { key: 'Level1_Low', label: 'Level1_Low', type: 'numeric', desc: 'A control level as a numeric column. Name it however you like — the header becomes the chart title.' },
  { key: 'Level2_High', label: 'Level2_High', type: 'numeric', desc: 'Add as many additional numeric columns as you have control levels; each gets its own Levey-Jennings chart.' },
]
const TEMPLATE_ROWS = [
  { Date: '2026-01-01', Level1_Low: 68.2, Level2_High: 262.4 },
  { Date: '2026-01-02', Level1_Low: 69.5, Level2_High: 258.1 },
  { Date: '2026-01-03', Level1_Low: 70.1, Level2_High: 264.7 },
]

export default function LeveyJenningsDemo({ onNavigate }) {
  const [rows, setRows] = useState([])
  const [columns, setColumns] = useState([])
  const [labelColumn, setLabelColumn] = useState(null)
  const [selectedLevels, setSelectedLevels] = useState([])
  const [overrides, setOverrides] = useState({})
  const [loadError, setLoadError] = useState(null)
  const [datasetName, setDatasetName] = useState(null)
  const [exporting, setExporting] = useState(false)
  const canvasRefs = useRef({})

  function onFile(file, name) {
    setLoadError(null)
    Papa.parse(file, {
      header: true, dynamicTyping: true, skipEmptyLines: true, comments: '#',
      complete: ({ data }) => {
        if (!data || data.length === 0) { alert('No rows parsed'); return }
        const keys = Object.keys(data[0])
        const valueCols = detectValueColumns(keys, data)
        if (valueCols.length === 0) { setLoadError('No numeric columns detected in this file.'); return }
        setRows(data)
        setColumns(valueCols)
        setLabelColumn(detectLabelColumn(keys))
        setSelectedLevels(valueCols)
        setOverrides({})
        setDatasetName(name)
      },
    })
  }

  function loadExample(file, label) {
    setLoadError(null)
    fetch(`/examples/${file}`)
      .then(r => { if (!r.ok) throw new Error(`${file} (${r.status})`); return r.text() })
      .then(t => onFile(new File([t], file, { type: 'text/csv' }), label))
      .catch(err => setLoadError(`Could not load example: ${err.message}`))
  }

  function toggleLevel(col) {
    setSelectedLevels(prev => prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col])
  }

  function setOverride(col, field, value) {
    setOverrides(prev => ({ ...prev, [col]: { ...prev[col], [field]: value === '' ? null : Number(value) } }))
  }

  function resetOverride(col) {
    setOverrides(prev => { const next = { ...prev }; delete next[col]; return next })
  }

  const levelData = useMemo(() => {
    return selectedLevels.map((col, i) => {
      const values = rows.map(r => Number(r[col])).filter(v => !Number.isNaN(v))
      const labels = labelColumn ? rows.map(r => r[labelColumn]) : values.map((_, idx) => idx + 1)
      const computedMean = mean(values)
      const computedSd = sd(values)
      const ov = overrides[col] || {}
      const activeMean = ov.mean != null ? ov.mean : computedMean
      const activeSd = ov.sd != null ? ov.sd : computedSd
      const safeSd = (activeSd === 0 || Number.isNaN(activeSd)) ? Number.EPSILON : activeSd
      const flagged = values
        .map((v, idx) => ({ v, idx }))
        .filter(({ v }) => Math.abs(v - activeMean) > 2 * safeSd)
        .map(({ v, idx }) => ({
          label: String(labels[idx]),
          value: Number(v).toFixed(3),
          sdFromMean: ((v - activeMean) / safeSd).toFixed(2),
        }))
      return {
        col, colorIndex: i, values, labels,
        computedMean, computedSd, activeMean, activeSd,
        usingOverride: ov.mean != null || ov.sd != null,
        n: values.length,
        cv: activeMean ? Number((activeSd / activeMean) * 100).toFixed(2) : 'n/a',
        min: values.length ? Math.min(...values).toFixed(3) : 'n/a',
        max: values.length ? Math.max(...values).toFixed(3) : 'n/a',
        flagged,
      }
    })
  }, [rows, selectedLevels, overrides, labelColumn])

  async function exportPdf() {
    if (levelData.length === 0) return
    setExporting(true)
    try {
      const { buildMonthlyReportPdf } = await import('../pdfReport')
      const period = labelColumn && rows.length
        ? `${rows[0][labelColumn]} – ${rows[rows.length - 1][labelColumn]}`
        : `Run 1 – ${rows.length}`
      const levels = levelData.map(l => {
        const canvas = canvasRefs.current[l.col]
        if (!canvas) return null
        return {
          name: l.col,
          canvas,
          stats: {
            n: l.n,
            mean: Number(l.activeMean).toFixed(3),
            sd: Number(l.activeSd).toFixed(3),
            cv: l.cv,
            min: l.min,
            max: l.max,
            target: l.usingOverride ? { mean: Number(l.activeMean).toFixed(3), sd: Number(l.activeSd).toFixed(3) } : null,
          },
          flagged: l.flagged,
        }
      }).filter(Boolean)

      const doc = buildMonthlyReportPdf({
        title: `Levey-Jennings Monthly QC Report${datasetName ? ` — ${datasetName}` : ''}`,
        period,
        levels,
      })
      doc.save(`levey-jennings-report-${new Date().toISOString().slice(0, 10)}.pdf`)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <div className="card">
        <div className="westgard-controls">
          <input type="file" accept=".csv,text/csv" onChange={e => e.target.files[0] && onFile(e.target.files[0], e.target.files[0].name)} />
          <span className="hint">Upload a CSV — every numeric column becomes its own control-level chart.</span>
        </div>

        <div className="westgard-controls">
          <span className="hint">Or load a dummy month of QC data:</span>
          {EXAMPLES.map(ex => (
            <button key={ex.key} className="btn btn-ghost" title={ex.hint} onClick={() => loadExample(ex.file, ex.label)}>
              {ex.label}
            </button>
          ))}
        </div>

        {loadError && <p className="hint" role="alert">{loadError}</p>}

        {columns.length > 0 && (
          <>
            <div className="rules-row">
              {columns.map(col => (
                <label key={col} className="rule-toggle">
                  <input type="checkbox" checked={selectedLevels.includes(col)} onChange={() => toggleLevel(col)} /> {col}
                </label>
              ))}
            </div>
            <div className="field-row">
              <button className="btn btn-primary" disabled={exporting || levelData.length === 0} onClick={exportPdf}>
                {exporting ? 'Building PDF…' : 'Export monthly report (PDF)'}
              </button>
              <span className="hint">Chart snapshots, stats, and flagged points per level, with a review &amp; approval page for sign-off.</span>
            </div>
          </>
        )}
      </div>

      {levelData.map(l => (
        <div className="card" key={l.col}>
          <div className="chart-wrap">
            <LevelChart
              ref={el => { canvasRefs.current[l.col] = el }}
              label={l.col}
              labels={l.labels}
              values={l.values}
              mean={l.activeMean}
              sd={l.activeSd}
              colorIndex={l.colorIndex}
            />
          </div>

          <div className="summary-grid">
            <div className="stat-tile"><strong>{l.n}</strong><span>Count</span></div>
            <div className="stat-tile"><strong>{Number(l.activeMean).toFixed(3)}</strong><span>Mean</span></div>
            <div className="stat-tile"><strong>{Number(l.activeSd).toFixed(3)}</strong><span>SD</span></div>
            <div className="stat-tile"><strong>{l.cv}%</strong><span>CV</span></div>
            <div className="stat-tile"><strong>{l.min}</strong><span>Min</span></div>
            <div className="stat-tile"><strong>{l.max}</strong><span>Max</span></div>
          </div>

          <details className="target-details">
            <summary>Set target mean / SD (optional — overrides computed values, as with an assigned control lot)</summary>
            <div className="field-row">
              <label className="hint" htmlFor={`mean-${l.col}`}>Target mean</label>
              <input id={`mean-${l.col}`} type="number" step="any" placeholder={l.computedMean.toFixed(3)}
                value={overrides[l.col]?.mean ?? ''} onChange={e => setOverride(l.col, 'mean', e.target.value)} />
              <label className="hint" htmlFor={`sd-${l.col}`}>Target SD</label>
              <input id={`sd-${l.col}`} type="number" step="any" min="0" placeholder={l.computedSd.toFixed(3)}
                value={overrides[l.col]?.sd ?? ''} onChange={e => setOverride(l.col, 'sd', e.target.value)} />
              {l.usingOverride && <button className="btn btn-ghost" onClick={() => resetOverride(l.col)}>Reset to computed</button>}
            </div>
          </details>

          <ul className="violations-list">
            {l.flagged.length === 0 && <li>All points within ±2 SD <span className="badge none">clean</span></li>}
            {l.flagged.map((f, i) => (
              <li key={i}>
                <div>
                  <span className="rule-code">{f.label}</span>
                  <span className="rule-desc">value {f.value}, {f.sdFromMean} SD from mean</span>
                </div>
                <span className="badge">±2SD</span>
              </li>
            ))}
          </ul>
        </div>
      ))}

      <DataTemplateCard
        title="Input data template"
        description="Levey-Jennings charts are typically run for a full month per control level, then reviewed and signed off by a lab director. Shape your CSV like this — one row per run, one column per control level:"
        columns={TEMPLATE_COLUMNS}
        sampleRows={TEMPLATE_ROWS}
        downloadFileName="levey-jennings-template.csv"
        note="Column names are free-form — anything matching Time/Date/Index/ID/Sample/Run/Seq/Point/Obs is treated as the x-axis label rather than a value column."
      />

      <div className="card">
        <h3>What is a Levey-Jennings chart?</h3>
        <p>
          A Levey-Jennings chart plots a control's QC results in run order against its established mean, with
          horizontal reference lines at ±1, ±2, and ±3 SD. It's the base visualization laboratories build on —
          Westgard multi-rules are then applied on top of it to decide whether a run should be accepted or
          rejected. Points beyond ±2 SD are flagged above for a quick look; for full multi-rule evaluation
          (1_2s, 1_3s, 2_2s, R4s, 4_1s, 10_x), see the{' '}
          {onNavigate
            ? <a href="#" onClick={e => { e.preventDefault(); onNavigate('westgard') }}>Westgard rules demo</a>
            : <span>Westgard rules demo</span>}.
        </p>
      </div>
    </div>
  )
}
