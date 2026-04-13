# 5 Research-Backed Project Ideas for Maxime Haegeman & Harsh Kakroo (April 2026)

*The following ideas are grounded in real market data, funding trends, regulatory timelines, and verified gaps from extensive web research conducted in April 2026.*

---

## Research Summary: Key Signals Driving These Ideas

| Signal | Data Point | Source |
|---|---|---|
| AI Act enforcement | Full enforcement **2 August 2026** — no dominant compliance platform exists | EU official timeline |
| Agent cost crisis | **71%** of developers say running AI agents costs more than building them; **72%** already over budget | 2026 State of Data Engineering |
| Game playtesting gap | Existing tools (Antidote, Lysto, Playcocola) are early-stage; **50% of studios** now use generative AI but no integrated playtesting platform dominates | BCG Gaming Report 2026 |
| AI fatigue in UX | Nielsen Norman Group calls 2026 "the year of AI fatigue" — users tired of lazy AI features, no tools exist to test AI trust/explainability | NN/g State of UX 2026 |
| Personalization gap | Only **Sequen** ($22M raised) is making big-tech recommendation infra accessible to mid-market; market at **$2.44B** growing to $3.62B by 2029 | TechCrunch, March 2026 |
| Research democratization noise | **61%** of orgs provide tools, but <50% offer guardrails — more research without quality control creates noise, not clarity | Maze Future of UX Research 2026 |
| Non-engineer AI eval | **78%** of AI failures are invisible; most eval tools require engineering. PMs and domain experts locked out | Confident AI, 2026 |
| EU sovereign AI demand | **60%** of Western European CIOs want local cloud providers; sovereign cloud market heading from EUR 20B to EUR 100B by 2031 | Akave, Broadcom |

---

## Project 1: TestPlay — AI-Powered Playtesting Platform for Game Studios

### The Problem
Game studios spend 15-25% of development time on playtesting, yet the process is still manual: recruit testers, run sessions, watch recordings, take notes, hope someone spots the pattern. Existing tools are fragmented — Antidote does remote streaming, Lysto does feedback analysis, Playcocola targets indies — but **no platform combines automated gameplay analysis, behavioral analytics, sentiment extraction, and UX heuristic evaluation in one workflow.**

Meanwhile, 50% of studios are adopting generative AI (BCG 2026), but none of the AI adoption is going toward the playtesting bottleneck.

### The Product
A platform where studios upload gameplay sessions (video + telemetry) and get back:
1. **Automated friction detection** — ML models identify where players hesitate, repeat actions, rage-quit, or deviate from intended paths
2. **Sentiment overlay** — NLP analysis of think-aloud audio and chat during sessions, timestamped and mapped to gameplay moments
3. **Heuristic scoring** — AI-driven evaluation against established game UX heuristics (Nielsen's adapted for games, PLAY heuristics), surfacing violations automatically
4. **Comparative analytics** — Cross-session pattern detection: "72% of testers got stuck at this exact corridor for 45+ seconds"
5. **Designer-ready reports** — Not raw data dumps, but prioritized, visual reports that game designers can act on without an analyst intermediary

### Who does what
- **Maxime:** Video + telemetry ingestion pipeline, ML models for behavioral pattern detection (player state classification, anomaly detection on gameplay sequences), NLP sentiment pipeline on think-aloud audio, scalable backend on Azure/Databricks. His telemetry infrastructure work at Massive is directly transferable.
- **Harsh:** UX heuristic framework embedded as evaluation criteria, report design and information architecture, user research with game designers and QA leads at Massive to validate what outputs are actually actionable. His Avatar and Star Wars Outlaws playtesting experience means he's been the user of tools like this.

### Market
- **Target:** AAA, AA, and funded indie studios (200+ studios globally spending $1M+ on QA/playtesting)
- **Size:** Game analytics tools market at **$638M** (2025), 5.7% CAGR to 2033. Playtesting is a sub-segment with no dominant platform.
- **Monetization:** SaaS per-seat + usage-based (per session analyzed). $500-$2K/month per studio.
- **Competitive edge:** Built by an ML engineer who builds game telemetry pipelines and a UX researcher who runs game playtests — at a AAA studio. No competitor has both.

### Why now (2026)
- 50% of studios using generative AI but not for playtesting (BCG)
- Vision-language models can now parse gameplay video reliably
- Live-service games need continuous playtesting, not one-shot pre-launch sessions
- GTA 6 launch in late 2026 will trigger a wave of live-service investment across the industry

### Risk
- Studios may prefer in-house solutions for IP protection
- **Mitigation:** On-prem deployment option, zero-retention data processing, SOC 2 compliance

---

## Project 2: AgentMeter — Cost Attribution & Optimization for AI Agent Workflows

### The Problem
71% of developers say operating AI agents costs more than building them. 72% have already exceeded their expected budgets. Yet there is no tool that tells you *why* your agent costs what it costs — which steps in a multi-agent workflow are expensive, which tool calls are redundant, where token waste accumulates, and what the cost per business outcome actually is.

Existing observability tools (Arize, Langfuse, Portkey) track traces and latency, but none provide **cost attribution at the business-outcome level** — the ability to say "this customer onboarding agent costs $2.34 per successful onboarding, but $8.71 per failed one, and 63% of the cost comes from the document parsing step."

### The Product
A lightweight SDK + dashboard that instruments AI agent workflows and provides:
1. **Per-step cost breakdown** — Token usage, API calls, tool invocations, and wall-clock time attributed to each step in multi-agent chains
2. **Cost-per-outcome tracking** — Map agent costs to business outcomes (successful task, failed task, human escalation), not just technical metrics
3. **Waste detection** — Identify redundant LLM calls, excessive retries, unnecessarily long prompts, and model over-specification (using GPT-4 where Haiku suffices)
4. **Optimization recommendations** — Actionable suggestions: "Switch step 3 to a smaller model to save 41% with <2% quality drop" backed by A/B test data
5. **Budget alerts & forecasting** — Predict monthly spend based on current usage patterns, alert before budget overruns

### Who does what
- **Maxime:** SDK instrumentation layer, cost aggregation pipeline (this is a data engineering problem at core — high-volume event ingestion, real-time aggregation, time-series analytics), ML models for waste detection and optimization recommendations. His Databricks/Spark background handles the data volume.
- **Harsh:** Dashboard UX designed for engineering managers and finance stakeholders (not just developers), alert design, onboarding flow, user research with teams actively deploying agents to understand what cost visibility they actually need.

### Market
- **Target:** Companies deploying AI agents in production (40% of enterprise apps will include agents by end of 2026 — Gartner)
- **Size:** AI observability market projected at **$10.7B by 2033** (22.5% CAGR). Cost optimization is a sub-segment growing faster than monitoring.
- **Monetization:** Usage-based SaaS. Free tier for <$500/month agent spend. Paid tiers at 2-5% of optimized savings (aligned incentives).
- **Competitive edge:** Existing tools (Arize, Langfuse) monitor *performance*. AgentMeter monitors *economics*. Different buyer (engineering manager / CFO vs. ML engineer).

### Why now (2026)
- 72% over budget on agents — this is an acute, measured pain point
- Agent adoption hitting 40% of enterprise apps means the cost problem is scaling fast
- MCP and A2A protocols standardizing agent architectures makes instrumentation more feasible
- OpenAI acquiring Promptfoo and Anthropic acquiring Humanloop signal that eval/observability is a validated category

### Risk
- Arize/Langfuse could add cost features
- **Mitigation:** Cost-per-outcome attribution is a fundamentally different data model than trace-based observability. It requires business logic integration, not just SDK instrumentation.

---

## Project 3: GuardRail — EU AI Act Compliance Platform for Mid-Market Companies

### The Problem
The EU AI Act's remaining provisions — especially for high-risk AI systems — become enforceable on **2 August 2026**. Each high-risk system requires conformity assessment costing EUR 5,000-50,000, with average initial compliance exceeding EUR 50,000 per system. Yet there is no dominant "Stripe for AI compliance" — no single platform handles risk classification, documentation, conformity assessment, and ongoing monitoring.

The existing players (nexos.ai at $350M valuation, Alinia, DAIKI) are early-stage and enterprise-focused. The mid-market (100-2,000 employees) deploying AI is completely underserved — too large to ignore the regulation, too small to hire a compliance team or afford enterprise contracts.

### The Product
A self-serve platform that guides companies through AI Act compliance:
1. **AI System Inventory** — Catalog all AI systems in use, automatically classify risk level (unacceptable / high / limited / minimal) using a guided questionnaire + automated detection
2. **Documentation Generator** — Produce the required technical documentation: dataset descriptions, training processes, risk assessments, human oversight measures — using templates populated by structured Q&A
3. **Conformity Assessment Prep** — Checklist-driven preparation for third-party conformity assessment, reducing assessor time (and cost) by arriving with complete documentation
4. **Ongoing Monitoring Dashboard** — Track compliance status across all AI systems, flag when model updates or use-case changes trigger re-assessment
5. **Incident Reporting** — Structured workflow for mandatory serious incident reporting to national authorities

### Who does what
- **Maxime:** Automated AI system detection (scanning codebases and infrastructure for ML models/API calls), risk classification engine, documentation generation pipeline using LLMs with structured templates, monitoring infrastructure for model drift and compliance status. His Azure/Databricks enterprise data experience makes the technical detection layer feasible.
- **Harsh:** Compliance workflow UX that non-legal, non-technical users can navigate, information architecture for complex regulatory requirements, onboarding research with mid-market companies to understand their actual compliance journey, report design that satisfies both internal stakeholders and external assessors.

### Market
- **Target:** European mid-market companies (100-2,000 employees) deploying AI — estimated 50,000+ companies
- **Size:** AI governance market growing from **$0.89B (2024) to $5.78B (2029)** at 45.3% CAGR. AI data governance spending hitting $492M in 2026 alone.
- **Monetization:** SaaS subscription tiered by number of AI systems. Starter (up to 5 systems): EUR 299/month. Growth (up to 25): EUR 799/month. Enterprise: custom.
- **Competitive edge:** EU-based founders (geographic trust + regulatory proximity), mid-market focus (enterprise competitors ignore this segment), self-serve UX (no mandatory sales calls).

### Why now (2026)
- **4 months until enforcement** — urgency is peaking
- nexos.ai raised $35M but targets enterprise; mid-market is unaddressed
- Companies deploying AI agents (40% by EOY 2026) multiply the number of systems requiring compliance
- EU Member States must establish regulatory sandboxes by August 2026 — creating a wave of awareness

### Risk
- Regulatory interpretation may shift post-enforcement
- **Mitigation:** Template-based approach allows rapid updates; partner with EU law firms for regulatory guidance layer

---

## Project 4: AIProof — AI Experience Testing Tool for Product Teams

### The Problem
Nielsen Norman Group declared 2026 "the year of AI fatigue." Users are tired of poorly implemented AI features. Yet there are **no purpose-built tools for testing AI-powered user experiences** — not the model accuracy (that's eval tools), but the *user experience* of AI: trust, explainability, failure recovery, expectation management, and perceived intelligence.

88% of UX researchers cite AI-assisted analysis as impactful, but zero tools exist for the inverse: **systematically testing how users experience AI features.** When an AI feature hallucinates, how does the UI handle it? When confidence is low, does the user know? When the AI fails, can the user recover without frustration?

### The Product
A testing platform specifically designed for AI-powered product experiences:
1. **AI Interaction Scenarios** — Pre-built test scripts for common AI UX patterns: chatbots, recommendation feeds, AI-generated content, auto-complete, smart search, copilots. Testers follow structured tasks that probe trust, comprehension, and failure handling.
2. **Trust & Transparency Scoring** — Proprietary framework measuring: Does the user understand what the AI did? Do they trust the output? Can they correct it? Do they know when it's uncertain?
3. **Failure Mode Testing** — Deliberately inject AI failures (hallucinations, latency spikes, low-confidence outputs, edge cases) and measure user reaction via behavioral tracking + post-task questionnaire
4. **Benchmarking** — Compare your AI UX against industry benchmarks: "Your chatbot's trust score is in the 34th percentile for fintech AI assistants"
5. **Actionable Report** — Not just scores, but specific UI recommendations: "Add a confidence indicator here," "Provide a fallback option when latency exceeds 3s"

### Who does what
- **Maxime:** Failure injection engine (programmatic hallucination generation, latency simulation, confidence manipulation), behavioral analytics pipeline (click patterns, time-on-task, correction frequency), benchmark data infrastructure, scoring model development.
- **Harsh:** Trust & Transparency scoring framework (this is a UX research methodology contribution — his core expertise), test scenario design based on 4+ years of UX research, report template design, user research with product teams to validate what AI UX metrics actually drive redesign decisions. His work testing AI experiences at Massive (Avatar, Star Wars Outlaws) is directly relevant.

### Market
- **Target:** Product teams building AI-powered features — from startups to enterprise. Secondary: UX research agencies offering AI UX audits as a service.
- **Size:** UX research tools market at **$1.5B**, growing 15%+ YoY. AI experience testing is a new sub-category with no incumbent.
- **Monetization:** SaaS. Free tier (3 tests/month), Pro ($79/mo per product), Team ($249/mo). Agency tier for UX consultancies.
- **Competitive edge:** Harsh's UX research methodology becomes the product's scoring framework — a defensible IP moat. No eval tool (Arize, Confident AI) tests the *user experience*; they test model performance. Different problem, different buyer.

### Why now (2026)
- AI fatigue is measurable and named (NN/g 2026) — product teams are feeling pressure to prove their AI features don't suck
- 78% of AI failures are invisible to developers but visible to users — someone needs to surface this gap
- More than half of designers concerned about AI's impact on design quality (NN/g) — they want proof, not vibes
- No tool owns this category yet — first-mover advantage is real

### Risk
- Could be perceived as "just another survey tool"
- **Mitigation:** The failure injection engine + behavioral analytics make this fundamentally different from Maze or UserTesting. You can't test AI trust by asking users to click buttons on a static prototype.

---

## Project 5: RecoBox — Plug-and-Play Recommendation Engine for Mid-Market Products

### The Problem
TikTok, Spotify, Netflix, and Amazon have recommendation systems built by 50-person ML teams with proprietary data flywheels. Everyone else — e-commerce stores, content platforms, SaaS products, marketplaces with 10K-1M users — either uses basic rule-based sorting ("most popular," "newest") or tries to build a recommendation system from scratch and fails.

Sequen ($22M raised, March 2026) is the only startup making big-tech recommendation infrastructure accessible, but they target consumer companies and require significant integration work. The mid-market needs something that works out of the box.

### The Product
A drop-in recommendation API that works with small datasets and zero ML expertise:
1. **5-minute integration** — Single API endpoint or JavaScript snippet. Send user events (views, clicks, purchases, likes), get ranked recommendations back. No model training, no feature engineering, no ML team required.
2. **Cold-start handling** — Works from day 1 with as few as 100 users using hybrid collaborative + content-based filtering, gracefully improving as data accumulates
3. **Multi-surface support** — Homepage feed, "similar items," "customers also bought," email recommendations, push notification targeting — all from one integration
4. **Explainable recommendations** — Every recommendation comes with a human-readable reason ("because you viewed X," "popular with similar users") for transparency and debugging
5. **A/B testing built in** — Split traffic between recommendation strategies and measure impact on conversion, engagement, and retention without external tools

### Who does what
- **Maxime:** Recommendation engine (collaborative filtering, content-based, hybrid models), real-time event ingestion pipeline, model serving infrastructure, cold-start algorithms, A/B testing framework. His scoring/propensity model experience (Anteriad: -25% outbound calls, BECQUET: -10% marketing costs) is this exact skill set applied to recommendations.
- **Harsh:** Integration UX (the "5-minute setup" experience), dashboard for non-technical users to understand and tune recommendations, A/B test results visualization, onboarding flow, user research with mid-market product teams to validate what level of control they actually want vs. what should be automated.

### Market
- **Target:** Mid-market e-commerce, content platforms, marketplaces, SaaS products (10K-1M users, $1M-$50M revenue)
- **Size:** Recommendation system market at **$2.44B** (2025), growing to $3.62B by 2029. Mid-market segment is the fastest-growing and least-served.
- **Monetization:** Usage-based API pricing. Free tier (up to 10K recommendations/month), Growth ($199/mo for 500K), Scale ($799/mo for 5M). Enterprise: custom.
- **Competitive edge:** Sequen targets large consumer companies with complex integrations. RecoBox targets the long tail with zero-config setup. Different market segment, different product philosophy. Maxime's proven track record with scoring/propensity models is the technical moat.

### Why now (2026)
- Sequen's $22M raise validated the market but left the mid-market unaddressed
- Personalization is now a user expectation, not a luxury — even for smaller products
- Inference costs have dropped enough to make per-API-call pricing viable at mid-market scale
- No-code/low-code movement means mid-market teams expect plug-and-play, not "hire an ML engineer"

### Risk
- AWS/GCP could commoditize recommendation APIs
- **Mitigation:** Cloud providers optimize for scale, not simplicity. AWS Personalize still requires ML knowledge. The moat is UX, not algorithms.

---

## Comparison Matrix

| | Time to MVP | Revenue Potential | Defensibility | Existing Assets | Urgency |
|---|---|---|---|---|---|
| 1. TestPlay | 8-10 wks | High (B2B) | Domain + data | Massive insider access | High |
| 2. AgentMeter | 6-8 wks | Very high (B2B) | Biz-outcome model | Maxime's data eng | Very high |
| 3. GuardRail | 6-8 wks | Very high (B2B) | Regulatory moat | EU-based founders | Critical (Aug 2026) |
| 4. AIProof | 6-8 wks | High (PLG) | Methodology IP | Harsh's UX research | High |
| 5. RecoBox | 8-10 wks | Very high (API) | UX simplicity | Maxime's scoring models | Medium |

## Top 3 Recommendations

### #1: GuardRail (Project 3)
**Why it wins:** The August 2026 deadline is a forcing function no other project has. 50,000+ mid-market European companies need compliance, no one serves them, and Maxime + Harsh are EU-based. The $5.78B market at 45.3% CAGR is the fastest-growing category in all the research. Time pressure means customers will pay now, not "eventually."

### #2: AgentMeter (Project 2)
**Why it's strong:** 72% over budget is a screaming pain point with a measurable dollar value. The cost-per-outcome framing is genuinely novel — no existing tool does this. The buyer is an engineering manager or VP, not a developer, which means higher ACV and stickier contracts.

### #3: AIProof (Project 4)
**Why it matters:** AI fatigue is real and named. Harsh's UX research methodology becomes defensible product IP — something no pure-engineering team can replicate. First-mover in a category that will exist whether or not they build it.
