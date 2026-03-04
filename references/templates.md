# Wes AI — knowledge.md Entry Guide

---

## Quick Checklist

- [ ] Heading follows the pattern: `System — Symptom or Topic`
- [ ] First sentence names the system and describes the behaviour
- [ ] Entry is written in plain prose, no bullet points, no backticks
- [ ] References placed at the bottom under `References:`
- [ ] Entry separated from neighbours with `---` above and below
- [ ] Entry added to the Index at the top of the file
- [ ] Run `python aiv2.py --reingest` after saving

---

## Entry Template

```
---

## [System] — [Symptom, Topic, or Fix]

[First sentence: name the system and describe the exact behaviour or scenario.]
[Second sentence: explain the cause or consequence.]
[Third sentence onward: provide the fix, steps, or additional context.]

References:
[URL or SAP Note if applicable]

---
```

---

## Heading Pattern

The heading is the most important part. It directly affects retrieval quality.

**Pattern:** `System — Symptom or Topic`

| Good | Why |
|------|-----|
| `BIB Replication — Employee Multiple Assignments Address Failure and BP Sync Fix` | Names system, names symptom, names downstream impact |
| `SuccessFactors OData — EmpPayCompRecurring Insert Behaviour and Delta Risk` | Names system, names entity, names behaviour and risk |
| `SAP Cloud Connector — Always Use Path and All Sub-paths` | Names system, states the rule directly |

| Bad | Why |
|-----|-----|
| `Address Replication Issue` | No system prefix, too vague |
| `BIB Fix` | No symptom, nothing for retrieval to match on |
| `SuccessFactors Thing I Learned` | Useless for retrieval |

**Rules:**
- Always start with the system name — this clusters related entries in retrieval
- Include the symptom or scenario in plain English — this is what queries match against
- If it is a fix or troubleshooting entry, say so — include words like `Failure`, `Fix`, `Error`, `Not Arriving`, `Not Replicating`
- If it involves a specific SAP entity name like `EmpPayCompRecurring`, include it in the heading — BM25 matches on it exactly

---

## First Sentence Rule

The first sentence must name the system and describe the behaviour. This is the most semantically loaded sentence in the entry — the embedding model weights it heavily.

**Good:**
```
When CPI is sending BIB replication data but S/4 or ECC is not receiving it,
check these two common causes.
```

**Bad:**
```
This entry covers a common issue.
```

If it is a troubleshooting entry, describe the exact symptom a consultant would experience.
If it is a how-it-works entry, describe what the system does.
If it is a configuration entry, describe what is being configured and why.

---

## Writing Rules

**Prose only — no bullet points, no numbered lists inside the entry body.**
The splitter and embedding model handle prose better than lists. Lists also tend to produce incomplete sentences that score poorly in retrieval.

Wrong:
```
- Check SICF service
- Check SCC access policy
```

Right:
```
Fix 1 — SICF service inactive: TCode SICF > navigate to default_host/sap/bc/srt/scs/sap/.
Fix 2 — SCC access policy wrong: set resource path to Path and All Sub-paths.
```

**No backticks, no Markdown formatting inside the entry body.**
The knowledge base is plain text. Backticks and bold are applied by the LLM in its output, not stored in the knowledge base.

**Use specific technical language.**
Include TCodes, entity names, field names, and configuration paths exactly as they appear in SAP. BM25 matches on these exactly.

**Frame uncertainty honestly.**
If a fix is a possible fix rather than a confirmed fix, say so. This prevents the LLM from stating uncertain information with false confidence.

---

## References

If the entry has SAP Notes, URLs, or Google Drive links, place them at the bottom under `References:`.

```
References:
https://me.sap.com/notes/2903776
https://drive.google.com/file/d/abc123/view
```

The system prompt instructs the LLM to include these verbatim in its response. If there are no references, omit the section entirely.

---

## Entry Separator

Every entry must be separated by `---` on its own line above and below. This is the primary chunk boundary the splitter respects.

```
---

## Entry One — Title

Entry one content.

---

## Entry Two — Title

Entry two content.

---
```

---

## Category Placement

Place the entry in the most relevant category. If unsure, use this guide:

| Category | What belongs here |
|----------|------------------|
| Integration Architecture | Foundational concepts, design decisions, delta strategies |
| SAP Integration Suite and CPI | CPI platform, iFlow behaviour, licensing, ATO/STP |
| BIB Replication | Anything involving BIB framework, S/4 replication, BP Sync |
| SuccessFactors OData API | OData entities, navigation, delta, API behaviour |
| SuccessFactors Configuration and Permissions | RBP, API user setup, object definitions, picklists |
| SuccessFactors Modules | Time Management, LMS, Recruiting, specific module behaviour |
| System Replication | Non-BIB replication flows, PTP, cost center replication |

If no category fits, create a new one and add a comment divider:

```
# ════════════════════════════════════════════════════
# CATEGORY 8 — New Category Name
# ════════════════════════════════════════════════════
```

---

## Index Update

After adding an entry, update the index at the top of the file:

```
Category: BIB Replication
- BIB Replication — What It Is and How It Works
- BIB Replication — Action Reason and BP Sync Behaviour
- BIB Replication Failure — Data Not Arriving at S4 or ECC
- BIB Replication — Employee Multiple Assignments Address Failure and BP Sync Fix  ← add here
- SAP Cloud Connector — Always Use Path and All Sub-paths
- SAPRouter — Purpose and When Required
```

---

## Full Example

```
---

## BIB Replication — Employee Multiple Assignments Address Replication Failure and BP Sync Fix

When SuccessFactors is configured with Employee Multiple Assignments and both assignments
are active, address data sometimes does not replicate correctly to S/4 or ECC. This causes
the BP Sync job to fail because a valid address is required for Business Partner creation.
A possible fix is to check whether Home and Host address is enabled in SuccessFactors —
enabling it has resolved this issue in known cases.

References:
https://me.sap.com/notes/2917035
https://me.sap.com/notes/2347654
https://me.sap.com/notes/2835695

---
```

---

## After Saving

Always reingest after editing knowledge.md:

```
python aiv2.py --reingest
```

The vector store and BM25 index will not reflect changes until reingest is complete.