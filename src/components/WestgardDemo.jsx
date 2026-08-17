import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import Papa from 'papaparse'
import DataTemplateCard from './DataTemplateCard'
import WestgardAnalyteCard from './WestgardAnalyteCard'

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
  { key: 'creatinine', label: 'Creatinine (Cr)', file: 'creatinine.csv', hint: 'random error spike → R4s' },
  { key: 'tsh', label: 'TSH', file: 'tsh.csv', hint: 'isolated blip → 1_2s only' },
  { key: 'hemoglobin', label: 'Hemoglobin (Hgb)', file: 'hemoglobin.csv', hint: 'brief low run → 4_1s' },
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

export default function WestgardDemo() {
  const [datasets, setDatasets] = useState([])
  const [enabledRules, setEnabledRules] = useState({ '1_2s': true, '1_3s': true, '2_2s': true, 'R4s': true, '4_1s': true, '10_x': true })
  const [loadError, setLoadError] = useState(null)

  function addDataset(id, name, data) {
    if (!data || data.length === 0) { setLoadError('No rows parsed'); return }
    const columns = Object.keys(data[0])
    setDatasets(prev => [...prev.filter(d => d.id !== id), { id, name, rows: data, columns }])
  }

  function removeDataset(id) {
    setDatasets(prev => prev.filter(d => d.id !== id))
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

  function toggleRule(rule) { setEnabledRules(prev => ({ ...prev, [rule]: !prev[rule] })) }

  return (
    <div>
      <div className="card">
        <div className="westgard-controls">
          <input type="file" accept=".csv,text/csv" onChange={e => e.target.files[0] && onFile(e.target.files[0])} />
          <span className="hint">Upload a CSV with a numeric column (header OK). Adds to the analytes below rather than replacing them.</span>
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

        <div className="rules-row">
          {Object.keys(enabledRules).map(r => (
            <label key={r} className="rule-toggle" title={RULE_INFO[r].description}>
              <input type="checkbox" checked={enabledRules[r]} onChange={() => toggleRule(r)} /> {r}
            </label>
          ))}
        </div>
      </div>

      {datasets.map(d => (
        <WestgardAnalyteCard
          key={d.id}
          id={d.id}
          name={d.name}
          rows={d.rows}
          columns={d.columns}
          enabledRules={enabledRules}
          ruleInfo={RULE_INFO}
          onRemove={removeDataset}
        />
      ))}

      <div className="card">
        <h3>What are Westgard rules?</h3>
        <p>Westgard multi-rules are a set of statistical checks applied to laboratory quality-control (QC) results before a batch of patient results is released. Each rule looks for a different pattern in the QC data relative to its established mean and standard deviation (SD) — a single extreme value, a run drifting to one side, and so on. A <span className="severity-pill warning">warning</span> hit means "worth a second look"; a <span className="severity-pill reject">reject</span> hit means the run likely has a real analytical error and shouldn't be released until it's investigated.</p>

        <div className="rule-info-grid">
          {Object.entries(RULE_INFO).map(([code, info]) => (
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
          <Link to="/levey-jennings">Levey-Jennings demo</Link> for a monthly, multi-level view with a PDF export.
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
