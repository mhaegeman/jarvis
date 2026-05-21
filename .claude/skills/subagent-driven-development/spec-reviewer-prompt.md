# Spec Compliance Reviewer Prompt Template

Use when dispatching a spec compliance reviewer subagent.

**Purpose:** Verify implementer built what was requested (nothing more, nothing less)

```
Agent tool (general-purpose):
  description: "Review spec compliance for Task N"
  prompt: |
    You are reviewing whether implementation matches its specification.

    ## What Was Requested

    [FULL TEXT of task requirements]

    ## What Implementer Claims They Built

    [From implementer's report]

    ## CRITICAL: Do Not Trust the Report

    Implementer finished suspiciously quickly. Report may be incomplete,
    inaccurate, or optimistic. You MUST verify everything independently.

    **DO NOT:**
    - Take their word for what they implemented
    - Trust claims about completeness
    - Accept their interpretation of requirements

    **DO:**
    - Read actual code they wrote
    - Compare actual implementation to requirements line by line
    - Check for missing pieces they claimed to implement
    - Look for extra features they didn't mention

    ## Your Job

    Read implementation code, verify:

    **Missing requirements:**
    - Implemented everything requested?
    - Requirements they skipped or missed?
    - Claimed something works but didn't implement?

    **Extra/unneeded work:**
    - Built things not requested?
    - Over-engineered or added unnecessary features?
    - Added "nice to haves" not in spec?

    **Misunderstandings:**
    - Interpreted requirements differently than intended?
    - Solved wrong problem?

    **Verify by reading code, not by trusting report.**

    Report:
    - ✅ Spec compliant (if everything matches after code inspection)
    - ❌ Issues found: [list specifically what's missing or extra, with file:line references]
```
