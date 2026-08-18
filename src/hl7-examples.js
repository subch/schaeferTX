// Synthetic HL7 v2.x example messages for the visualizer demo.
// All patient data here is fabricated for demonstration only.

export const HL7_EXAMPLES = [
  {
    id: 'order',
    label: 'Order (ORM^O01)',
    description: 'A lab order placed by a physician for a Complete Blood Count.',
    message:
`MSH|^~\\&|LAB_SYS|SCHAEFERTX_LAB|HIS|SCHAEFERTX_HOSP|20260817101500||ORM^O01|MSG00001|P|2.3
PID|1||MRN100234^^^SCHAEFERTX^MR||DOE^JANE^A||19800115|F|||123 MAIN ST^^ANYTOWN^TX^75001||(555)555-0100|||S||ACCT9001
PV1|1|O|LAB^^^SCHAEFERTX||||1234^SMITH^ROBERT^^^^MD|||LAB|||||||||V0001
ORC|NW|ORD1001^LAB_SYS|||||||20260817101500|1234^SMITH^ROBERT
OBR|1|ORD1001^LAB_SYS||CBC^Complete Blood Count^L|||20260817100000|||||||||1234^SMITH^ROBERT`
  },
  {
    id: 'result',
    label: 'Result (ORU^R01)',
    description: 'Lab results for the CBC order above, with a technologist note.',
    message:
`MSH|^~\\&|LAB_SYS|SCHAEFERTX_LAB|HIS|SCHAEFERTX_HOSP|20260817113000||ORU^R01|MSG00002|P|2.3
PID|1||MRN100234^^^SCHAEFERTX^MR||DOE^JANE^A||19800115|F
PV1|1|O|LAB^^^SCHAEFERTX
ORC|RE|ORD1001^LAB_SYS|RES1001^LAB_SYS
OBR|1|ORD1001^LAB_SYS|RES1001^LAB_SYS|CBC^Complete Blood Count^L|||20260817100000|||||||||1234^SMITH^ROBERT|||||||20260817112000|||F
OBX|1|NM|WBC^White Blood Cell Count^L||7.2|10*3/uL|4.0-11.0|N|||F
OBX|2|NM|HGB^Hemoglobin^L||13.5|g/dL|12.0-16.0|N|||F
OBX|3|NM|PLT^Platelet Count^L||250|10*3/uL|150-400|N|||F
NTE|1||Sample slightly hemolyzed; results may be affected.`
  },
  {
    id: 'document',
    label: 'Document / Bedded PDF (MDM^T02)',
    description: 'A radiology report delivered as an embedded PDF (base64 truncated for the demo).',
    message:
`MSH|^~\\&|DOC_SYS|SCHAEFERTX_HOSP|HIS|SCHAEFERTX_HOSP|20260817140000||MDM^T02|MSG00003|P|2.3
EVN|T02|20260817140000
PID|1||MRN100234^^^SCHAEFERTX^MR||DOE^JANE^A||19800115|F
PV1|1|O|RAD^^^SCHAEFERTX
TXA|1|RA|TEXT|||20260817135000|||1234^SMITH^ROBERT|||DOC5001^DOC_SYS||||AU|||AV
OBX|1|ED|DOC5001^Radiology Report PDF^L||^Application^PDF^Base64^JVBERi0xLjQKJc-TRUNCATED-DEMO-DATA|||||F`
  },
  {
    id: 'ack',
    label: 'Acknowledgement (ACK)',
    description: 'The HIS confirming it accepted the original order message.',
    message:
`MSH|^~\\&|HIS|SCHAEFERTX_HOSP|LAB_SYS|SCHAEFERTX_LAB|20260817101501||ACK^O01|MSG00001-ACK|P|2.3
MSA|AA|MSG00001|Message accepted`
  }
]
