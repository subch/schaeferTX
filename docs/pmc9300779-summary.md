# PMC9300779 — summary and actionable points

This document contains a concise summary of key points from the paper available at https://pmc.ncbi.nlm.nih.gov/articles/PMC9300779/ and suggested actions for laboratory QC practice.

Summary (site-ready)
- Westgard multi-rules remain a practical method for detecting analytical errors, but their sensitivity and specificity vary with assay performance (imprecision, bias, sigma metrics). More sensitive rules detect more errors but may increase false positives.
- Control limits matter: short-term sample mean/SD can misrepresent long-term variability. Consider using long-term target values, user-supplied mean/SD, or robust estimators (median + MAD→SD) when appropriate.
- Combine multi-rules with sigma-metric and risk-based assessment: high-sigma assays can tolerate simpler rules, while low-sigma assays need stricter monitoring and corrective action thresholds.
- Sequence-based rules need sufficient run length and are affected by autocorrelation; validate rule choices with retrospective data analysis or simulation to understand false positive/negative rates.
- Operational recommendations: tailor rules per assay, visualize rule context clearly to aid interpretation, and re-evaluate QC strategy after method changes.

Suggested site copy (short):
"Recent literature highlights that Westgard rules are useful but must be adapted per assay. Match rule sensitivity to assay sigma performance, prefer long-term or robust estimates for control limits when available, and combine multi-rules with risk-based decision-making to balance detection power and false alarms. See the linked paper for details."
