import { jsPDF } from 'jspdf'

// Builds a printable/reviewable monthly QC summary: one page per control
// level with its Levey-Jennings chart and flagged points, followed by a
// review & approval page for the analyst and laboratory director to sign.
// levels: [{ name, canvas, stats: {n,mean,sd,cv,min,max,target}, flagged: [{label,value,sdFromMean}] }]
export function buildMonthlyReportPdf({ title, period, levels }) {
  const doc = new jsPDF({ unit: 'pt', format: 'letter' })
  const pageWidth = doc.internal.pageSize.getWidth()
  const pageHeight = doc.internal.pageSize.getHeight()
  const margin = 44
  let y = margin

  function ensureRoom(needed) {
    if (y + needed > pageHeight - margin) { doc.addPage(); y = margin }
  }

  doc.setFontSize(16)
  doc.text(title, margin, y); y += 22
  doc.setFontSize(10)
  doc.setTextColor(110)
  doc.text(`Period: ${period}`, margin, y); y += 14
  doc.text(`Generated: ${new Date().toLocaleString()}`, margin, y); y += 24
  doc.setTextColor(0)

  levels.forEach((lvl, idx) => {
    if (idx > 0) { doc.addPage(); y = margin }

    doc.setFontSize(13)
    doc.text(lvl.name, margin, y); y += 18

    const imgW = pageWidth - margin * 2
    const imgH = imgW * (lvl.canvas.height / lvl.canvas.width)
    const dataUrl = lvl.canvas.toDataURL('image/png', 1.0)
    doc.addImage(dataUrl, 'PNG', margin, y, imgW, imgH)
    y += imgH + 16

    doc.setFontSize(10)
    doc.setTextColor(30)
    const s = lvl.stats
    doc.text(`N: ${s.n}    Mean: ${s.mean}    SD: ${s.sd}    CV%: ${s.cv}    Min: ${s.min}    Max: ${s.max}`, margin, y)
    y += 15
    if (s.target) {
      doc.setTextColor(110)
      doc.text(`Target mean/SD in use: ${s.target.mean} / ${s.target.sd} (manual override)`, margin, y)
      doc.setTextColor(30)
      y += 15
    }
    y += 6

    doc.setFontSize(11)
    doc.text('Points beyond ±2 SD (for reviewer attention):', margin, y); y += 15
    doc.setFontSize(9.5)
    doc.setTextColor(70)
    if (lvl.flagged.length === 0) {
      doc.text('None — all points within ±2 SD.', margin + 10, y); y += 13
    } else {
      lvl.flagged.forEach(f => {
        ensureRoom(16)
        doc.text(`• ${f.label}: ${f.value}  (${f.sdFromMean} SD from mean)`, margin + 10, y)
        y += 13
      })
    }
    doc.setTextColor(0)
  })

  doc.addPage()
  y = margin
  doc.setFontSize(14)
  doc.text('Review & Approval', margin, y); y += 24
  doc.setFontSize(10)
  doc.setTextColor(110)
  doc.text('This monthly QC summary is provided for documentation and review. Verify against', margin, y); y += 14
  doc.text('laboratory-established target ranges and current SOPs before sign-off.', margin, y); y += 32
  doc.setTextColor(0)

  function signatureLine(label) {
    ensureRoom(60)
    doc.setDrawColor(120)
    doc.line(margin, y, margin + 260, y)
    doc.line(margin + 300, y, margin + 460, y)
    y += 14
    doc.setFontSize(9)
    doc.setTextColor(110)
    doc.text(`${label} — Signature`, margin, y)
    doc.text('Date', margin + 300, y)
    doc.setTextColor(0)
    y += 32
    doc.setFontSize(10)
  }

  signatureLine('Analyst / Reviewer')
  signatureLine('Laboratory Director (Approval)')

  y += 8
  doc.setFontSize(10)
  doc.text('Comments:', margin, y); y += 18
  for (let i = 0; i < 3; i++) {
    ensureRoom(20)
    doc.setDrawColor(190)
    doc.line(margin, y, pageWidth - margin, y)
    y += 20
  }

  return doc
}
