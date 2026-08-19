import { describe, it, expect } from 'vitest'
import { evaluateWestgard } from '../src/westgard'

// Rules are evaluated against a provided target mean/SD (as in real QC use,
// where limits come from the established lot target, not from the same handful
// of points being evaluated). The original tests computed mean/SD from the
// 5-point sample itself, which let the outlier inflate the SD so much that no
// rule could ever fire — they had been failing silently since introduction
// (CI only runs build, not test).
const TARGET = { providedMean: 100, providedSd: 1 }

describe('Westgard evaluator basic cases', () => {
  it('detects 1_3s (single outlier)', () => {
    const values = [100, 100.5, 99.5, 100, 104] // last point far beyond 3SD
    const { points } = evaluateWestgard(values, TARGET)
    const last = points[4]
    expect(last.rules.map(r => r.name)).toContain('1_3s')
  })

  it('detects 2_2s (two consecutive beyond 2SD same side)', () => {
    const values = [100, 100.5, 102.5, 102.6, 100] // middle two beyond +2SD
    const { points } = evaluateWestgard(values, TARGET)
    expect(points[2].rules.map(r => r.name)).toContain('2_2s')
    expect(points[3].rules.map(r => r.name)).toContain('2_2s')
  })

  it('detects R4s (opposite-signed pair with range >= 4SD)', () => {
    const values = [100, 100, 102.5, 97.5, 100] // range 5SD, opposite sides
    const { points } = evaluateWestgard(values, TARGET)
    const triggered = points.some(p => p.rules.some(r => r.name === 'R4s'))
    expect(triggered).toBe(true)
  })

  it('detects 4_1s (four consecutive beyond 1SD same side)', () => {
    const values = [100, 101.5, 101.4, 101.6, 101.5, 100]
    const { points } = evaluateWestgard(values, TARGET)
    const flagged = [1, 2, 3, 4].every(i => points[i].rules.some(r => r.name === '4_1s'))
    expect(flagged).toBe(true)
  })

  it('detects 10_x (ten in a row same side)', () => {
    const values = Array.from({ length: 12 }, (_, i) => 100 + (i < 11 ? 0.3 : 0))
    const { points } = evaluateWestgard(values, TARGET)
    const has10 = points.some(p => p.rules.some(r => r.name === '10_x'))
    expect(has10).toBe(true)
  })

  it('flags nothing on in-control data', () => {
    const values = [100, 100.4, 99.6, 100.2, 99.8, 100.1]
    const { points } = evaluateWestgard(values, TARGET)
    expect(points.every(p => p.rules.length === 0)).toBe(true)
  })
})
