// Shared helpers for picking usable numeric columns out of parsed CSV data.

// Columns that look like a row index/timestamp rather than QC data, so the
// column auto-picker skips them in favor of actual measured values.
export const NON_VALUE_COLUMN = /^(time|date|index|idx|id|sample|run|seq|point|obs)$/i

// Returns the subset of `keys` that hold numeric values somewhere in `data`
// and don't look like an index/time/id column.
export function detectValueColumns(keys, data) {
  return keys.filter(k => !NON_VALUE_COLUMN.test(k) && data.some(r => typeof r[k] === 'number'))
}

// Returns the first column that looks like a row index/timestamp, for use as
// an x-axis label, falling back to null (caller should use a 1-based index).
export function detectLabelColumn(keys) {
  return keys.find(k => NON_VALUE_COLUMN.test(k)) || null
}
