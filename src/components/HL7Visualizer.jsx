import React, { useState, useMemo } from 'react'
import { parseHL7, getSegmentColor, getSegmentDef, getFieldInfo } from '../hl7-parser'
import { HL7_EXAMPLES } from '../hl7-examples'
import '../styles-hl7.css'

export default function HL7Visualizer(){
  const [raw, setRaw] = useState(HL7_EXAMPLES[0].message)
  const [activeExample, setActiveExample] = useState(HL7_EXAMPLES[0].id)
  const [selected, setSelected] = useState(null) // {segIndex, fieldNum}

  const { segments, error } = useMemo(()=> parseHL7(raw), [raw])

  const presentTypes = useMemo(()=>{
    const seen = []
    segments.forEach(s=>{ if (!seen.includes(s.type)) seen.push(s.type) })
    return seen
  }, [segments])

  function loadExample(ex){
    setRaw(ex.message)
    setActiveExample(ex.id)
    setSelected(null)
  }

  function selectField(segIndex, fieldNum){
    setSelected(prev => (prev && prev.segIndex===segIndex && prev.fieldNum===fieldNum) ? null : { segIndex, fieldNum })
  }

  const selectedDetail = useMemo(()=>{
    if (!selected) return null
    const seg = segments[selected.segIndex]
    if (!seg) return null
    const field = seg.fields.find(f=>f.num===selected.fieldNum)
    if (!field) return null
    return {
      segType: seg.type,
      segName: getSegmentDef(seg.type).name,
      fieldNum: field.num,
      description: getFieldInfo(seg.type, field.num),
      value: field.value,
      components: field.components && field.components.length > 1 ? field.components : null
    }
  }, [selected, segments])

  return (
    <div>
      <h2>HL7 Message Visualizer</h2>

      <div className="hl7-phi-banner">
        <span>⚠️</span>
        <div>
          <strong>Demonstration tool — do not use with real patient data.</strong> Parsing happens entirely
          in your browser; nothing you paste or load here is transmitted to a server or saved anywhere.
          Even so, this is a teaching demo, not a validated clinical tool — please don't paste actual PHI into it.
        </div>
      </div>

      <div className="card">
        <div className="hl7-examples">
          {HL7_EXAMPLES.map(ex=>(
            <button
              key={ex.id}
              className={activeExample===ex.id ? 'active' : ''}
              onClick={()=>loadExample(ex)}
              title={ex.description}
            >
              {ex.label}
            </button>
          ))}
        </div>

        <div className="hl7-input-row">
          <textarea
            className="hl7-textarea"
            value={raw}
            onChange={e=>{ setRaw(e.target.value); setActiveExample(null); setSelected(null) }}
            spellCheck="false"
          />
        </div>
        <div style={{color:'var(--text-muted)', fontSize:'0.85em'}}>
          Paste your own message above (assumes standard | ^ ~ \ & delimiters), or click a field below to see what it means.
        </div>

        {error && <div className="hl7-error">{error}</div>}

        {segments.length > 0 && (
          <div className="hl7-message">
            {segments.map(seg=>{
              const color = getSegmentColor(seg.type)
              return (
                <div className="hl7-segment-row" key={seg.index}>
                  <div className="hl7-segment-label" style={{background:color}} title={getSegmentDef(seg.type).name}>
                    {seg.type}
                  </div>
                  <div className="hl7-segment-fields">
                    {seg.fields.map(f=>{
                      const isSelected = selected && selected.segIndex===seg.index && selected.fieldNum===f.num
                      const isEmpty = f.value === ''
                      return (
                        <button
                          key={f.num}
                          className={`hl7-field-chip ${isSelected?'selected':''} ${isEmpty?'empty':''}`}
                          onClick={()=>selectField(seg.index, f.num)}
                          title={getFieldInfo(seg.type, f.num)}
                        >
                          <span className="field-num">{seg.type}-{f.num}</span>{isEmpty ? '(empty)' : f.value}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {selectedDetail && (
          <div className="hl7-detail-panel">
            <div className="detail-title">{selectedDetail.segType}-{selectedDetail.fieldNum} · {selectedDetail.segName}</div>
            <div>{selectedDetail.description}</div>
            <div className="detail-value">{selectedDetail.value || '(empty)'}</div>
            {selectedDetail.components && (
              <div className="detail-components">
                Components: {selectedDetail.components.map((c,i)=> `${i+1}: ${c || '(empty)'}`).join('  |  ')}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="card">
        <h3>How to read this</h3>
        <p>
          An HL7 v2 message is a stack of <strong>segments</strong> (one per line), each starting with a
          three-letter code like <code>PID</code> or <code>OBX</code>. Within a segment, fields are separated
          by <code>|</code>, and a field can itself hold <strong>components</strong> separated by <code>^</code>
          — for example a patient name field splits into family, given, and middle name components. Click any
          field chip above to see its number, meaning, and raw value.
        </p>
      </div>

      <div className="card">
        <h3>Segment glossary {presentTypes.length > 0 && <span style={{color:'var(--text-muted)', fontWeight:400}}>— segments in this message</span>}</h3>
        <table className="hl7-glossary-table">
          <thead>
            <tr><th>Segment</th><th>Name</th><th>Purpose</th></tr>
          </thead>
          <tbody>
            {(presentTypes.length > 0 ? presentTypes : ['MSH','PID','PV1','ORC','OBR','OBX']).map(type=>{
              const def = getSegmentDef(type)
              return (
                <tr key={type}>
                  <td><span className="hl7-glossary-swatch" style={{background:getSegmentColor(type)}}></span>{type}</td>
                  <td>{def.name}</td>
                  <td>{def.description}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
