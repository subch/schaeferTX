// Enhanced Westgard evaluator
export function mean(values){
  const n = values.length
  const s = values.reduce((a,b)=>a+(+b||0),0)
  return s/n
}

export function sd(values, sample=true){
  const m = mean(values)
  const sq = values.reduce((a,b)=>a+Math.pow((+b||0)-m,2),0)
  const denom = sample ? Math.max(1, values.length-1) : values.length
  return Math.sqrt(sq/denom)
}

export function median(values){
  const s = [...values].sort((a,b)=>a-b)
  const n = s.length
  if (n===0) return NaN
  const mid = Math.floor(n/2)
  return n%2===0 ? (s[mid-1]+s[mid])/2 : s[mid]
}

export function mad(values){
  const m = median(values)
  const dev = values.map(v=>Math.abs(v-m))
  return median(dev)
}

// Convert MAD to an approximate SD assuming normal distribution
export function madToSd(madValue){
  return madValue / 0.6745
}

// Evaluate Westgard multi-rules. Returns an object {summary, points}
// points: [{index, value, rules: [{name,severity}] }]
// options:
//  - useRobust (boolean): use median+MAD->sd instead of mean+sd
//  - providedMean, providedSd: numbers to use instead of computed
//  - enabledRules: object with boolean flags per rule
export function evaluateWestgard(values, options = {}){
  const { useRobust=false, providedMean=null, providedSd=null, enabledRules=null } = options
  if (!Array.isArray(values)) throw new Error('values must be array')
  const n = values.length
  if (n===0) return {summary:{n:0}, points:[]}

  const m = providedMean !== null ? providedMean : (useRobust ? median(values) : mean(values))
  const s = providedSd !== null ? providedSd : (useRobust ? madToSd(mad(values)) : sd(values))

  // guard against zero SD
  const safeSd = (s === 0 || Number.isNaN(s)) ? Number.EPSILON : s

  const beyond = (v,k)=> Math.abs(v - m) > k * safeSd
  const side = v => (v > m ? 1 : (v < m ? -1 : 0))

  const defaultEnabled = { '1_2s': true, '1_3s': true, '2_2s': true, 'R4s': true, '4_1s': true, '10_x': true }
  const enabled = Object.assign({}, defaultEnabled, enabledRules || {})

  // prepare points
  const points = values.map((v,i)=>({index:i, value: v, rules: []}))

  // 1_3s and 1_2s
  values.forEach((v,i)=>{
    if (enabled['1_3s'] && beyond(v,3)) points[i].rules.push({name:'1_3s', severity:'reject'})
    else if (enabled['1_2s'] && beyond(v,2)) points[i].rules.push({name:'1_2s', severity:'warning'})
  })

  // 2_2s: two consecutive beyond 2SD on same side
  if (enabled['2_2s']){
    for (let i=1;i<n;i++){
      if (beyond(values[i],2) && beyond(values[i-1],2) && side(values[i])===side(values[i-1]) && side(values[i])!==0){
        points[i].rules.push({name:'2_2s', severity:'reject'})
        points[i-1].rules.push({name:'2_2s', severity:'reject'})
      }
    }
  }

  // R4s: two consecutive with range >= 4SD (one above, one below)
  if (enabled['R4s']){
    for (let i=1;i<n;i++){
      if (Math.abs(values[i] - values[i-1]) >= 4 * safeSd && side(values[i]) !== side(values[i-1])){
        points[i].rules.push({name:'R4s', severity:'reject'})
        points[i-1].rules.push({name:'R4s', severity:'reject'})
      }
    }
  }

  // 4_1s: four consecutive beyond 1SD on same side
  if (enabled['4_1s']){
    for (let i=3;i<n;i++){
      const groupIdx = [i-3,i-2,i-1,i]
      const groupVals = groupIdx.map(j=>values[j])
      const groupSides = groupVals.map(v=>side(v))
      const allBeyond = groupVals.every(v=> Math.abs(v - m) > 1 * safeSd)
      const sameSide = groupSides.every(s=> s === groupSides[0] && s !== 0)
      if (allBeyond && sameSide){
        groupIdx.forEach(j=> points[j].rules.push({name:'4_1s', severity:'reject'}))
      }
    }
  }

  // 10_x: ten consecutive on same side
  if (enabled['10_x']){
    for (let i=9;i<n;i++){
      const groupIdx = Array.from({length:10},(_,k)=>i-9+k)
      const groupVals = groupIdx.map(j=>values[j])
      const groupSides = groupVals.map(v=>side(v))
      const sameSide = groupSides.every(s=> s === groupSides[0] && s !== 0)
      if (sameSide){
        groupIdx.forEach(j=> points[j].rules.push({name:'10_x', severity:'reject'}))
      }
    }
  }

  // deduplicate rules per point (by name)
  points.forEach(p=>{
    const seen = new Set()
    p.rules = p.rules.filter(r => (seen.has(r.name) ? false : (seen.add(r.name), true)))
  })

  // summary
  const summary = {
    n,
    mean: m,
    sd: s,
    computedSd: safeSd,
    counts: {}
  }
  points.forEach(p=> p.rules.forEach(r=> summary.counts[r.name] = (summary.counts[r.name]||0)+1))

  return {summary, points}
}
