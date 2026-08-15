// Simple Westgard evaluator and statistics
export function mean(values){
  const n = values.length
  const s = values.reduce((a,b)=>a+(+b||0),0)
  return s/n
}
export function sd(values, sample=true){
  const m = mean(values)
  const sq = values.reduce((a,b)=>a+Math.pow((+b||0)-m,2),0)
  const denom = sample ? (values.length-1) : values.length
  return Math.sqrt(sq/denom)
}

export function evaluateWestgard(values){
  const m = mean(values)
  const s = sd(values)
  const res = []
  const side = v => (v > m ? 1 : (v < m ? -1 : 0))
  const beyond = (v, k) => Math.abs(v-m) > k * s

  values.forEach((v,i)=>{
    if (beyond(v,3)) res.push({index:i, rule:'1_3s', severity:'reject'})
    else if (beyond(v,2)) res.push({index:i, rule:'1_2s', severity:'warning'})
  })

  for (let i=1;i<values.length;i++){
    if (beyond(values[i],2) && beyond(values[i-1],2) && side(values[i])===side(values[i-1])){
      res.push({index:i, rule:'2_2s', severity:'reject'})
      res.push({index:i-1, rule:'2_2s', severity:'reject'})
    }
  }

  for (let i=1;i<values.length;i++){
    if (Math.abs(values[i]-values[i-1]) >= 4*s){
      res.push({index:i, rule:'R4s', severity:'reject'})
      res.push({index:i-1, rule:'R4s', severity:'reject'})
    }
  }

  for (let i=3;i<values.length;i++){
    const group = values.slice(i-3,i+1)
    if (group.every(v=>beyond(v,1) && side(v)===side(group[0]))){
      group.forEach((_,k)=>res.push({index:i-3+k, rule:'4_1s', severity:'reject'}))
    }
  }

  for (let i=9;i<values.length;i++){
    const group = values.slice(i-9,i+1)
    if (group.every(v => side(v)===side(group[0]) && side(v)!==0)){
      group.forEach((_,k)=>res.push({index:i-9+k, rule:'10_x', severity:'reject'}))
    }
  }

  const key = r => `${r.index}|${r.rule}`
  const uniq = {}
  return res.filter(r => (uniq[key(r)] ? false : (uniq[key(r)] = true)))
}
