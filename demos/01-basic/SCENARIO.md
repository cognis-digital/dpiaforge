# Demo 01 - HR resume-screening AI

A company deploys an AI system that scores and ranks job applicants, then
filters out candidates automatically. This is a textbook high-risk scenario:

* **GDPR Art.35 / WP248**: evaluation/scoring, automated decisions with
  significant effect, processing on a large scale, and (potentially) vulnerable
  subjects -> multiple criteria met -> a DPIA is *required*.
* **EU AI Act Annex III(4)**: AI used in recruitment / selection of natural
  persons -> **HIGH_RISK** -> full provider obligations (Art.9-15, conformity
  assessment, EU-database registration).

## Run it

```bash
python -m dpiaforge --format table assess demos/01-basic/activity.json
# JSON for piping into other tooling:
python -m dpiaforge --format json assess demos/01-basic/activity.json
```

The tool reports `DPIA_REQUIRED`, `HIGH_RISK`, an elevated residual-risk band,
and the matching provider obligation checklist. Because mitigations are listed,
the residual score is reduced below the inherent score.
