import React, {useRef, useEffect, useState} from 'react'
import Papa from 'papaparse'
import { Chart, registerables } from 'chart.js'
import { mean, sd, evaluateWestgard } from '../westgard'
Chart.register(...registerables)

export default function WestgardDemo(){
  const canvasRef = useRef(null)
  const chartRef = useRef(null)
  const [summary, setSummary] = useState(null)

  useEffect(()=>{
    return ()=>{
      if (chartRef.current){
        chartRef.current.destroy()
        chartRef.current = null
      }
    }
  },[])

  function parseFile(file){
    Papa.parse(file, {
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: ({data}) => {
        if (!data || data.length === 0){
          alert('No rows parsed')
          return
        }
        // find first numeric column
        const keys = Object.keys(data[0])
        let col = null
        for (const k of keys){
          if (data.some(r=>typeof r[k] === 'number')){ col = k; break }
        }
        if (!col){
          alert('No numeric column found')
          return
        }
        const values = data.map(r=>Number(r[col])).filter(v=>!Number.isNaN(v))
        renderChart(values)
      }
    })
  }

  function renderChart(values){
    const m = mean(values)
    const s = sd(values)
    const violations = evaluateWestgard(values)
    setSummary({n: values.length, mean: m, sd: s, violations})

    const labels = values.map((_,i)=>i+1)
    const pointBackground = values.map((v,i)=> violations.find(x=>x.index===i) ? (violations.find(x=>x.index===i).severity==='reject' ? 'rgba(255,82,82,1)' : 'rgba(255,195,0,1)') : 'rgba(99,255,200,0.9)')

    const data = {
      labels,
      datasets: [{
        label: 'QC value',
        data: values,
        borderColor: 'rgba(111,184,255,0.9)',
        backgroundColor: 'rgba(111,184,255,0.2)',
        pointBackgroundColor: pointBackground,
        tension: 0.2,
        pointRadius: 4
      }]
    }

    const bands = [1,2,3]
    const plugins = []

    const config = {
      type: 'line',
      data,
      options: {
        responsive: true,
        interaction: {mode: 'index', intersect: false},
        scales: { y: { beginAtZero: false } },
        plugins: {
          legend: { display: false }
        }
      }
    }

    if (chartRef.current){ chartRef.current.destroy(); chartRef.current = null }
    chartRef.current = new Chart(canvasRef.current.getContext('2d'), config)

    // draw horizontal bands for mean +-1/2/3 sd using chart API
    const ctx = canvasRef.current.getContext('2d')
    const chart = chartRef.current
    chart.options.animation = false
    chart.update()

    // We will add horizontal lines as additional datasets (transparent)
    bands.forEach((k, idx)=>{
      chart.data.datasets.push({
        label: `±${k}SD`,
        data: labels.map(()=> m + k*s),
        fill: false,
        borderColor: idx===0 ? 'rgba(93,212,184,0.25)' : idx===1 ? 'rgba(111,184,255,0.18)' : 'rgba(111,184,255,0.12)',
        borderDash: [6,4],
        pointRadius: 0,
        tension: 0
      })
      chart.data.datasets.push({
        label: `±${k}SD lower`,
        data: labels.map(()=> m - k*s),
        fill: false,
        borderColor: idx===0 ? 'rgba(93,212,184,0.25)' : idx===1 ? 'rgba(111,184,255,0.18)' : 'rgba(111,184,255,0.12)',
        borderDash: [6,4],
        pointRadius: 0,
        tension: 0
      })
    })
    chart.update()
  }

  return (
    <div>
      <h2>Westgard rule explainer & demo</h2>
      <div className="card">
        <div className="westgard-controls">
          <input type="file" accept=".csv,text/csv" onChange={e=>{ if (e.target.files[0]) parseFile(e.target.files[0]) }} />
          <div style={{color:'var(--muted)'}}>Upload a CSV with a numeric column (header OK). First numeric column will be used.</div>
        </div>

        <div className="chart-wrap">
          <canvas ref={canvasRef} />
        </div>

        {summary && (
          <div style={{marginTop:12}}>
            <strong>Summary:</strong>
            <div>Count: {summary.n} | Mean: {summary.mean.toFixed(3)} | SD: {summary.sd.toFixed(3)}</div>
            <div className="legend">
              <div className="item"><span className="swatch" style={{background:'rgba(255,82,82,1)'}}></span> Reject</div>
              <div className="item"><span className="swatch" style={{background:'rgba(255,195,0,1)'}}></span> Warning</div>
              <div className="item"><span className="swatch" style={{background:'rgba(99,255,200,0.9)'}}></span> OK</div>
            </div>
            <div style={{marginTop:8}}>
              <strong>Violations:</strong>
              <ul>
                {summary.violations.map((v,i)=> <li key={i}>Index {v.index+1}: {v.rule} ({v.severity})</li>)}
              </ul>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <h3>How it works</h3>
        <p>This demo computes the mean and sample standard deviation of the uploaded QC series and evaluates common Westgard rules. Files are parsed in your browser and are not uploaded to any server.</p>
      </div>
    </div>
  )
}
