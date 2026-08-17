import React, { useRef, useEffect, forwardRef, useImperativeHandle } from 'react'
import { Chart, registerables } from 'chart.js'
Chart.register(...registerables)

const LEVEL_COLORS = ['rgba(111,184,255,0.9)', 'rgba(194,139,255,0.9)', 'rgba(102,224,196,0.9)', 'rgba(255,168,111,0.9)']

// A single Levey-Jennings chart for one control level: the run plus mean and
// +-1/2/3 SD bands. Exposes its <canvas> DOM node via ref so a parent can
// snapshot it (canvas.toDataURL) for the PDF export.
const LevelChart = forwardRef(function LevelChart({ label, labels, values, mean, sd, colorIndex = 0 }, forwardedRef) {
  const canvasRef = useRef(null)
  const chartRef = useRef(null)

  useImperativeHandle(forwardedRef, () => canvasRef.current, [])

  useEffect(() => {
    return () => { if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null } }
  }, [])

  useEffect(() => {
    if (!canvasRef.current || values.length === 0) return
    const safeSd = (sd === 0 || Number.isNaN(sd)) ? Number.EPSILON : sd
    const color = LEVEL_COLORS[colorIndex % LEVEL_COLORS.length]
    const pointBg = values.map(v => Math.abs(v - mean) > 3 * safeSd ? 'rgba(255,82,82,1)' : Math.abs(v - mean) > 2 * safeSd ? 'rgba(255,195,0,1)' : color)

    const data = {
      labels,
      datasets: [{
        label,
        data: values,
        borderColor: color,
        backgroundColor: color.replace('0.9', '0.12'),
        pointBackgroundColor: pointBg,
        tension: 0.15,
        pointRadius: 4,
      }],
    }

    const bandStyle = [
      { k: 1, color: 'rgba(102,224,196,0.22)' },
      { k: 2, color: 'rgba(255,200,74,0.22)' },
      { k: 3, color: 'rgba(255,107,107,0.22)' },
    ]
    bandStyle.forEach(({ k, color: bc }) => {
      data.datasets.push({ label: `+${k}SD`, data: labels.map(() => mean + k * safeSd), pointRadius: 0, borderColor: bc, borderDash: [6, 4], tension: 0 })
      data.datasets.push({ label: `-${k}SD`, data: labels.map(() => mean - k * safeSd), pointRadius: 0, borderColor: bc, borderDash: [6, 4], tension: 0 })
    })
    data.datasets.push({ label: 'Mean', data: labels.map(() => mean), pointRadius: 0, borderColor: 'rgba(238,243,248,0.55)', borderDash: [2, 3], tension: 0 })

    const config = {
      type: 'line',
      data,
      options: {
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        scales: { y: { beginAtZero: false } },
        plugins: { legend: { display: false }, title: { display: true, text: label, color: '#eef3f8', font: { size: 13, weight: '600' } } },
      },
    }

    if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null }
    chartRef.current = new Chart(canvasRef.current.getContext('2d'), config)
  }, [label, labels, values, mean, sd, colorIndex])

  return <canvas ref={canvasRef} />
})

export default LevelChart
