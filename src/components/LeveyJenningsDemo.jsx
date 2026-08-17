import React, { useRef, useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import Papa from 'papaparse'
import { mean, sd } from '../westgard'
import { detectValueColumns, detectLabelColumn } from '../dataUtils'
import LevelChart from './LevelChart'
import DataTemplateCard from './DataTemplateCard'

const EXAMPLES = [
  { key: 'glucose', label: 'Glucose', file: 'lj-glucose.csv', hint: '2 levels, stable in-control month' },
  { key: 'electrolytes', label: 'Sodium', file: 'lj-electrolytes.csv', hint: '2 levels, Level 2 drifting upward' },
  { key: 'lipids', label: 'Cholesterol', file: 'lj-lipids.csv', hint: '2 levels, Level 1 single outlier' },
  { key: 'creatinine', label: 'Creatinine', file: 'lj-creatinine.csv', hint: '2 levels, Level 2 single outlier' },
  { key: 'hemoglobin', label: 'Hemoglobin', file: 'lj-hemoglobin.csv', hint: '2 levels, Level 1 gradual drift' },
]

const KEY_SEP = '::'
const compositeKey = (datasetId, col) => `${datasetId}${KEY_SEP}${col}`
const splitKey = (key) => { const i = key.indexOf(KEY_SEP); return [key.slice(0, i), key.slice(i + KEY_SEP.length)] }

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

export default function LeveyJenningsDemo() {
  const [datasets, setDatasets] = useState([]) // [{id, name, rows, columns, labelColumn}]
  const [selectedLevels, setSelectedLevels] = useState([]) // composite keys
  const [overrides, setOverrides] = useState({}) // keyed by composite key
  const [loadError, setLoadError] = useState(null)
  const [exporting, setExporting] = useState(false)
  const canvasRefs = useRef({})

  function addDataset(id, name, data) {
    if (!data || data.length === 0) { setLoadError('No rows parsed'); return }
    const keys = Object.keys(data[0])
    const valueCols = detectValueColumns(keys, data)
    if (valueCols.length === 0) { setLoadError(`No numeric columns detected in ${name}.`); return }
    const labelColumn = detectLabelColumn(keys)
    setDatasets(prev => [...prev.filter(d => d.id !== id), { id, name, rows: data, columns: valueCols, labelColumn }])
    setSelectedLevels(prev => [...prev, ...valueCols.map(c => compositeKey(id, c))])
  }

  function removeDataset(id) {
    setDatasets(prev => prev.filter(d => d.id !== id))
    setSelectedLevels(prev => prev.filter(k => splitKey(k)[0] !== id))
    setOverrides(prev => {
      const next = { ...prev }
      Object.keys(next).forEach(k => { if (splitKey(k)[0] === id) delete next[k] })
      return next
    })
  }

  function onFile(file) {
    setLoadError(null)
    Papa.parse(file, {
      header: true, dynamicTyping: true, skipEmptyLines: true, comments: '#',
      complete: ({ data }) => addDataset(`upload-${Date.now()}`, file.name, data),
    })
  }

  function toggleExample(ex) {
    const isLoaded = datasets.some(d => d.id === ex.key)
    if (isLoaded) { removeDataset(ex.key); return }
    setLoadError(null)
    fetch(`/examples/${ex.file}`)
      .then(r => { if (!r.ok) throw new Error(`${ex.file} (${r.status})`); return r.text() })
      .then(t => new Promise((resolve, reject) => {
        Papa.parse(t, { header: true, dynamicTyping: true, skipEmptyLines: true, comments: '#', complete: resolve, error: reject })
      }))
      .then(({ data }) => addDataset(ex.key, ex.label, data))
      .catch(err => setLoadError(`Could not load example: ${err.message}`))
  }

  function toggleLevel(key) {
    setSelectedLevels(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key])
  }

  function setOverride(key, field, value) {
    setOverrides(prev => ({ ...prev, [key]: { ...prev[key], [field]: value === '' ? null : Number(value) } }))
  }

  function resetOverride(key) {
    setOverrides(prev => { const next = { ...prev }; delete next[key]; return next })
  }

  const levelData = useMemo(() => {
    return selectedLevels.map((key, i) => {
      const [datasetId, col] = splitKey(key)
      const ds = datasets.find(d => d.id === datasetId)
      if (!ds) return null
      const values = ds.rows.map(r => Number(r[col])).filter(v => !Number.isNaN(v))
      const labels = ds.labelColumn ? ds.rows.map(r => r[ds.labelColumn]) : values.map((_, idx) => idx + 1)
      const computedMean = mean(values)
      const computedSd = sd(values)
      const ov = overrides[key] || {}
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
        key, datasetId, col, colorIndex: i, values, labels,
        name: `${ds.name} — ${col}`,
        computedMean, computedSd, activeMean, activeSd,
        usingOverride: ov.mean != null || ov.sd != null,
        n: values.length,
        cv: activeMean ? Number((activeSd / activeMean) * 100).toFixed(2) : 'n/a',
        min: values.length ? Math.min(...values).toFixed(3) : 'n/a',
        max: values.length ? Math.max(...values).toFixed(3) : 'n/a',
        flagged,
      }
    }).filter(Boolean)
  }, [datasets, selectedLevels, overrides])

  async function exportPdf() {
    if (levelData.length === 0) return
    setExporting(true)
    try {
      const { buildMonthlyReportPdf } = await import('../pdfReport')
      const period = datasets
        .filter(ds => levelData.some(l => l.datasetId === ds.id))
        .map(ds => {
          const range = ds.labelColumn ? `${ds.rows[0][ds.labelColumn]} – ${ds.rows[ds.rows.length - 1][ds.labelColumn]}` : `Run 1 – ${ds.rows.length}`
          return `${ds.name}: ${range}`
        }).join('; ')
      const levels = levelData.map(l => {
        const canvas = canvasRefs.current[l.key]
        if (!canvas) return null
        return {
          name: l.name,
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
        title: 'Levey-Jennings Monthly QC Report',
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
          <input type="file" accept=".csv,text/csv" onChange={e => e.target.files[0] && onFile(e.target.files[0])} />
          <span className="hint">Upload a CSV — adds to the analytes below rather than replacing them. Every numeric column becomes its own control-level chart.</span>
        </div>

        <div className="westgard-controls">
          <span className="hint">Or select dummy analytes to compare (loads/unloads instantly):</span>
        </div>
        <div className="rules-row">
          {EXAMPLES.map(ex => (
            <label key={ex.key} className="rule-toggle" title={ex.hint}>
              <input type="checkbox" checked={datasets.some(d => d.id === ex.key)} onChange={() => toggleExample(ex)} /> {ex.label}
            </label>
          ))}
        </div>

        {loadError && <p className="hint" role="alert">{loadError}</p>}

        {datasets.length > 0 && (
          <>
            <div className="rules-row">
              {datasets.map(ds => ds.columns.map(col => {
                const key = compositeKey(ds.id, col)
                return (
                  <label key={key} className="rule-toggle">
                    <input type="checkbox" checked={selectedLevels.includes(key)} onChange={() => toggleLevel(key)} /> {ds.name} — {col}
                  </label>
                )
              }))}
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
        <div className="card" key={l.key}>
          <div className="chart-wrap">
            <LevelChart
              ref={el => { canvasRefs.current[l.key] = el }}
              label={l.name}
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
              <label className="hint" htmlFor={`mean-${l.key}`}>Target mean</label>
              <input id={`mean-${l.key}`} type="number" step="any" placeholder={l.computedMean.toFixed(3)}
                value={overrides[l.key]?.mean ?? ''} onChange={e => setOverride(l.key, 'mean', e.target.value)} />
              <label className="hint" htmlFor={`sd-${l.key}`}>Target SD</label>
              <input id={`sd-${l.key}`} type="number" step="any" min="0" placeholder={l.computedSd.toFixed(3)}
                value={overrides[l.key]?.sd ?? ''} onChange={e => setOverride(l.key, 'sd', e.target.value)} />
              {l.usingOverride && <button className="btn btn-ghost" onClick={() => resetOverride(l.key)}>Reset to computed</button>}
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
          (1_2s, 1_3s, 2_2s, R4s, 4_1s, 10_x), see the <Link to="/westgard">Westgard rules demo</Link>.
        </p>
      </div>
    </div>
  )
}
