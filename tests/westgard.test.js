import { describe, it, expect } from 'vitest'
import { evaluateWestgard } from '../src/westgard'

describe('Westgard evaluator basic cases', ()=>{
  it('detects 1_3s (single outlier)', ()=>{
    const values = [100, 101, 99, 100, 300] // last point far out
    const { points } = evaluateWestgard(values)
    const last = points[4]
    expect(last.rules.map(r=>r.name)).toContain('1_3s')
  })

  it('detects 2_2s (two consecutive beyond 2SD same side)', ()=>{
    const values = [100, 101, 104, 105, 100] // middle two high
    const { points } = evaluateWestgard(values)
    expect(points[2].rules.map(r=>r.name)).toContain('2_2s')
    expect(points[3].rules.map(r=>r.name)).toContain('2_2s')
  })

  it('detects R4s (opposite-signed pair with range >=4SD)', ()=>{
    const values = [100, 100, 110, 90, 100]
    const { points } = evaluateWestgard(values)
    // depending on SD this synthetic should trigger an R4s between 3 and 4
    const triggered = points.some(p=> p.rules.some(r=> r.name==='R4s'))
    expect(triggered).toBe(true)
  })

  it('detects 10_x (ten in a row same side)', ()=>{
    const values = Array.from({length:12},(_,i)=>100 + (i<11?1:0)) // first 11 slightly above mean
    const { points } = evaluateWestgard(values)
    const has10 = points.some(p=> p.rules.some(r=> r.name==='10_x'))
    expect(has10).toBe(true)
  })
})
