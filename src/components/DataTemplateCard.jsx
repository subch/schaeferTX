import React from 'react'
import Papa from 'papaparse'

// Renders a preview of the CSV shape a demo expects: a sample table plus
// plain-language notes, so a real dataset can be shaped to match without
// guessing at the parser's column-detection rules.
export default function DataTemplateCard({ title = 'Input data template', description, columns, sampleRows, note, downloadFileName }) {
  function downloadTemplate() {
    const csv = Papa.unparse(sampleRows.map(row => {
      const out = {}
      columns.forEach(col => { out[col.label] = row[col.key] })
      return out
    }))
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = downloadFileName || 'template.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="card template-card">
      <div className="template-card-head">
        <h3>{title}</h3>
        {downloadFileName && <button className="btn btn-ghost" onClick={downloadTemplate}>Download template CSV</button>}
      </div>
      {description && <p>{description}</p>}

      <div className="template-table-wrap">
        <table className="template-table">
          <thead>
            <tr>
              {columns.map(col => (
                <th key={col.key}>
                  {col.label}
                  {col.type && <span className="template-col-type">{col.type}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sampleRows.map((row, i) => (
              <tr key={i}>
                {columns.map(col => <td key={col.key}>{row[col.key]}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="template-notes">
        {columns.map(col => (
          <li key={col.key}><span className="rule-code">{col.label}</span> — {col.desc}</li>
        ))}
      </ul>

      {note && <p className="hint">{note}</p>}
    </div>
  )
}
