import React, {useRef, useEffect, useState} from 'react'
import Papa from 'papaparse'
import { Chart, registerables } from 'chart.js'
import { mean, sd, evaluateWestgard } from '../westgard'
Chart.register(...registerables)

export default function WestgardDemo(){
  const canvasRef = useRef(null)
  const chartRef = useRef(null)
  const [summary, setSummary] = useState(null)
  const [columns, setColumns] = useState([])
  const [selectedCol, setSelectedCol] = useState(null)
  const [rows, setRows] = useState([])
  const [enabledRules, setEnabledRules] = useState({ '1_2s': true, '1_3s': true, '2_2s': true, 'R4s': true, '4_1s': true, '10_x': true })

  useEffect(()=>{
    return ()=>{
      if (chartRef.current){
        chartRef.current.destroy()
        chartRef.current = null
      }
    }
  },[])

  function onFile(file){
    Papa.parse(file, { header: true, dynamicTyping: true, skipEmptyLines: true, complete: ({data, meta})=>{
      if (!data || data.length === 0){ alert('No rows parsed'); return }
      setRows(data)
      const keys = Object.keys(data[0])
      setColumns(keys)
      // pick first numeric column if present
      let col = null
      for (const k of keys){ if (data.some(r=> typeof r[k] === 'number')){ col = k; break } }
      setSelectedCol(col || keys[0])
    }})
  }

  function runAnalysis(col){
    if (!col) return
    const values = rows.map(r=>Number(r[col])).filter(v=>!Number.isNaN(v))
    const res = evaluateWestgard(values, { enabledRules })
    setSummary(res.summary)
    renderChart(values, res.points, res.summary)
  }

  function renderChart(values, points, summary){
    const labels = values.map((_,i)=>i+1)
    const pointBg = points.map(p=> p.rules.some(r=> r.severity==='reject') ? 'rgba(255,82,82,1)' : p.rules.some(r=> r.severity==='warning') ? 'rgba(255,195,0,1)' : 'rgba(99,255,200,0.9)')

    const data = { labels, datasets: [{ label: 'QC value', data: values, borderColor: 'rgba(111,184,255,0.9)', backgroundColor: 'rgba(111,184,255,0.12)', pointBackgroundColor: pointBg, pointRadius: 4, tension:0.2 }] }

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
      <h2>Westgard rule explainer & demo</h2>
      <div className="card">
        <div style={{display:'flex',gap:12,alignItems:'center',marginBottom:12}}>
          <input type="file" accept=".csv,text/csv" onChange={e=> e.target.files[0] && onFile(e.target.files[0])} />
          <div style={{color:'var(--muted)'}}>Upload a CSV with a numeric column (header OK). First numeric column will be suggested.</div>
          <button onClick={()=>{ // load example CSV via fetch from repository raw URL
            fetch('/examples/na_spikes.csv').then(r=>r.text()).then(t=>{
              const file = new File([t],'na_spikes.csv',{type:'text/csv'})
              onFile(file)
            })
          }}>Load example (Na+ spikes)</button>
        </div>

        {columns.length>0 && (
          <div style={{marginBottom:12}}>
            <label style={{color:'var(--muted)'}}>Select column:</label>
            <select value={selectedCol||''} onChange={e=>{ setSelectedCol(e.target.value); runAnalysis(e.target.value) }}>
              {columns.map(c=> <option key={c} value={c}>{c}</option>)}
            </select>
            <button style={{marginLeft:8}} onClick={()=>runAnalysis(selectedCol)}>Analyze</button>
            <button style={{marginLeft:8}} onClick={exportAnnotated}>Export Annotated CSV</button>
          </div>
        )}

        <div style={{display:'flex',gap:12,flexWrap:'wrap'}}>
          {Object.keys(enabledRules).map(r=> (
            <label key={r} style={{display:'inline-flex',alignItems:'center',gap:8}}>
              <input type="checkbox" checked={enabledRules[r]} onChange={()=>toggleRule(r)} /> {r}
            </label>
          ))}
        </div>

        <div className="chart-wrap" style={{marginTop:12}}>
          <canvas ref={canvasRef} />
        </div>

        {summary && (
          <div style={{marginTop:12}}>
            <strong>Summary:</strong>
            <div>Count: {summary.n} | Mean: {Number(summary.mean).toFixed(3)} | SD: {Number(summary.sd).toFixed(3)}</div>
            <div style={{marginTop:8}}>
              <strong>Violations:</strong>
              <ul>
                {summary && Object.entries(summary.counts).length===0 && <li>None detected</li>}
                {summary && Object.entries(summary.counts).map(([rule,c])=> <li key={rule}>{rule}: {c}</li>)}
              </ul>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <h3>Notes and references</h3>
        <p>This implementation follows the standard Westgard multi-rules (1_2s (warning), 1_3s, 2_2s, R4s, 4_1s, 10_x). For more background and the classical descriptions see <a href="https://www.westgard.com/westgard-rules.html" target="_blank" rel="noreferrer">westgard.com</a>.</p>
      </div>
    </div>
  )
}
