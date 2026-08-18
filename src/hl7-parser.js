// Minimal HL7 v2.x parser and glossary for the visualizer demo.
// Parses pipe-delimited segments/fields/components; does not resolve
// escape sequences or repetition (~) — out of scope for a teaching tool.

const SEGMENT_COLORS = {
  MSH: '#66e0c4',
  EVN: '#c28bff',
  PID: '#7fc7ff',
  PV1: '#ffc84a',
  ORC: '#ff9f6b',
  OBR: '#8bd4a8',
  OBX: '#7fe0e0',
  NTE: '#c9d1e0',
  TXA: '#ff8fa3',
  MSA: '#a8b4ff',
}
const DEFAULT_COLOR = '#9aa8bd'

const SEGMENT_DEFS = {
  MSH: { name: 'Message Header', description: 'Identifies the message type, sending/receiving systems, and routing/timing metadata. Every HL7 message starts with one.' },
  EVN: { name: 'Event Type', description: 'Describes the trigger event and when it occurred, most often seen in ADT (admit/discharge/transfer) messages.' },
  PID: { name: 'Patient Identification', description: 'Demographic and identifying information about the patient — name, date of birth, sex, address, identifiers.' },
  PV1: { name: 'Patient Visit', description: 'Visit-specific information: patient class, location, attending provider, and admission details.' },
  ORC: { name: 'Common Order', description: 'Order-level control information shared by all orders in an ORM/ORU message — who ordered what, and its current status.' },
  OBR: { name: 'Observation Request', description: 'Describes a single test or battery being ordered or resulted, such as a CBC panel.' },
  OBX: { name: 'Observation/Result', description: 'One reported result or observation value, with its units, reference range, and abnormal flag.' },
  NTE: { name: 'Notes and Comments', description: 'Free-text notes attached to the segment immediately preceding it.' },
  TXA: { name: 'Document Notification', description: 'Metadata about a transcribed or scanned document, such as a radiology report.' },
  MSA: { name: 'Message Acknowledgment', description: 'Confirms whether a previously sent message was accepted or rejected.' },
}
const DEFAULT_SEGMENT_DEF = { name: 'Unrecognized segment', description: "This segment type isn't in the demo glossary — consult the HL7 v2.x standard for its definition." }

const FIELD_DEFS = {
  MSH: {
    1: 'Field Separator', 2: 'Encoding Characters', 3: 'Sending Application', 4: 'Sending Facility',
    5: 'Receiving Application', 6: 'Receiving Facility', 7: 'Date/Time of Message', 8: 'Security',
    9: 'Message Type', 10: 'Message Control ID', 11: 'Processing ID', 12: 'Version ID',
    13: 'Sequence Number', 14: 'Continuation Pointer', 15: 'Accept Acknowledgment Type',
    16: 'Application Acknowledgment Type', 17: 'Country Code', 18: 'Character Set',
  },
  EVN: {
    1: 'Event Type Code', 2: 'Recorded Date/Time', 3: 'Date/Time Planned Event',
    4: 'Event Reason Code', 5: 'Operator ID', 6: 'Event Occurred',
  },
  PID: {
    1: 'Set ID', 2: 'Patient ID (external)', 3: 'Patient Identifier List', 4: 'Alternate Patient ID',
    5: 'Patient Name', 6: "Mother's Maiden Name", 7: 'Date/Time of Birth', 8: 'Administrative Sex',
    9: 'Patient Alias', 10: 'Race', 11: 'Patient Address', 12: 'County Code',
    13: 'Phone Number — Home', 14: 'Phone Number — Business', 15: 'Primary Language',
    16: 'Marital Status', 17: 'Religion', 18: 'Patient Account Number', 19: 'SSN Number',
    20: "Driver's License Number",
  },
  PV1: {
    1: 'Set ID', 2: 'Patient Class', 3: 'Assigned Patient Location', 4: 'Admission Type',
    5: 'Preadmit Number', 6: 'Prior Patient Location', 7: 'Attending Doctor', 8: 'Referring Doctor',
    9: 'Consulting Doctor', 10: 'Hospital Service', 11: 'Temporary Location',
    12: 'Preadmit Test Indicator', 13: 'Re-admission Indicator', 14: 'Admit Source',
    15: 'Ambulatory Status', 16: 'VIP Indicator', 17: 'Admitting Doctor', 18: 'Patient Type',
    19: 'Visit Number',
  },
  ORC: {
    1: 'Order Control', 2: 'Placer Order Number', 3: 'Filler Order Number', 4: 'Placer Group Number',
    5: 'Order Status', 6: 'Response Flag', 7: 'Quantity/Timing', 8: 'Parent',
    9: 'Date/Time of Transaction', 10: 'Entered By', 11: 'Verified By', 12: 'Ordering Provider',
    13: "Enterer's Location", 14: 'Call Back Phone Number',
  },
  OBR: {
    1: 'Set ID', 2: 'Placer Order Number', 3: 'Filler Order Number', 4: 'Universal Service Identifier',
    5: 'Priority', 6: 'Requested Date/Time', 7: 'Observation Date/Time', 8: 'Observation End Date/Time',
    9: 'Collection Volume', 10: 'Collector Identifier', 11: 'Specimen Action Code', 12: 'Danger Code',
    13: 'Relevant Clinical Info', 14: 'Specimen Received Date/Time', 15: 'Specimen Source',
    16: 'Ordering Provider', 17: 'Order Callback Phone Number', 18: 'Placer Field 1',
    19: 'Placer Field 2', 20: 'Filler Field 1', 21: 'Filler Field 2',
    22: 'Results Rpt/Status Change Date/Time', 23: 'Charge to Practice', 24: 'Diagnostic Serv Sect ID',
    25: 'Result Status',
  },
  OBX: {
    1: 'Set ID', 2: 'Value Type', 3: 'Observation Identifier', 4: 'Observation Sub-ID',
    5: 'Observation Value', 6: 'Units', 7: 'References Range', 8: 'Abnormal Flags',
    9: 'Probability', 10: 'Nature of Abnormal Test', 11: 'Observation Result Status',
    12: 'Date Last Observation Normal', 13: 'User Defined Access Checks',
    14: 'Date/Time of the Observation',
  },
  NTE: { 1: 'Set ID', 2: 'Source of Comment', 3: 'Comment' },
  TXA: {
    1: 'Set ID', 2: 'Document Type', 3: 'Document Content Presentation', 4: 'Activity Date/Time',
    5: 'Primary Activity Provider Code/Name', 6: 'Origination Date/Time', 7: 'Transcription Date/Time',
    8: 'Edit Date/Time', 9: 'Originator Code/Name', 10: 'Assigned Document Authenticator',
    11: 'Transcriptionist Code/Name', 12: 'Unique Document Number', 13: 'Parent Document Number',
    14: 'Placer Order Number', 15: 'Filler Order Number', 16: 'Unique Document File Name',
    17: 'Document Completion Status', 18: 'Document Confidentiality Status',
    19: 'Document Availability Status', 20: 'Document Storage Status',
  },
  MSA: {
    1: 'Acknowledgment Code', 2: 'Message Control ID', 3: 'Text Message',
    4: 'Expected Sequence Number', 5: 'Delayed Acknowledgment Type', 6: 'Error Condition',
  },
}

export function getSegmentColor(type){
  return SEGMENT_COLORS[type] || DEFAULT_COLOR
}

export function getSegmentDef(type){
  return SEGMENT_DEFS[type] || DEFAULT_SEGMENT_DEF
}

export function getFieldInfo(type, num){
  const label = FIELD_DEFS[type] && FIELD_DEFS[type][num]
  if (label) return `${type}-${num}: ${label}`
  return `${type}-${num} — not cataloged in this demo; see the HL7 v2.x spec for the full field list.`
}

export function parseHL7(raw){
  if (!raw || !raw.trim()) return { segments: [], error: null }

  const lines = raw.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n')
    .map(l => l.trimEnd())
    .filter(l => l.length > 0)

  if (lines.length === 0) return { segments: [], error: null }
  if (!lines[0].startsWith('MSH') || lines[0].length < 8) {
    return { segments: [], error: 'Message must start with a valid MSH segment (need at least "MSH|^~\\&|").' }
  }

  const fieldSep = lines[0][3]
  const afterSep = lines[0].slice(4)
  const nextSepIdx = afterSep.indexOf(fieldSep)
  const encodingChars = nextSepIdx === -1 ? afterSep : afterSep.slice(0, nextSepIdx)
  const componentSep = encodingChars[0] || '^'

  const segments = lines.map((line, index) => {
    const type = line.slice(0, 3)
    let fieldTokens
    if (type === 'MSH') {
      const rest = line.slice(4)
      fieldTokens = [fieldSep, ...rest.split(fieldSep)]
    } else {
      fieldTokens = line.split(fieldSep).slice(1)
    }

    const fields = fieldTokens.map((value, i) => {
      const num = i + 1
      const components = (type === 'MSH' && num <= 2) ? [value] : value.split(componentSep)
      return { num, value, components }
    })

    return { index, type, fields }
  })

  return { segments, error: null }
}
