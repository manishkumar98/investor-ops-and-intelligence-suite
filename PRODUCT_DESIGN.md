# Product Design: Investor Ops & Intelligence Suite

## 1. USERS

**Primary Users:**
- **Retail investors** — Comparing mutual fund schemes, seeking factual information
- **Fintech customer support teams** — Handling repetitive MF questions at scale
- **Product & Support teams** — Generating structured internal insights from customer feedback
- **Financial advisors** — Scheduling consultations and reviewing customer context
- **Investor relations teams** — Understanding customer sentiment trends

**Secondary Users:**
- **Content teams** — Creating standardized fee explanations
- **Compliance teams** — Ensuring no investment advice is given

---

## 2. PAIN POINTS

**For Retail Investors:**
- ❌ Scattered information across multiple sources (AMC, SEBI, AMFI websites)
- ❌ No unified way to ask complex questions combining facts + fees (e.g., *"What is exit load AND why was I charged?"*)
- ❌ Difficult to book advisor consultations quickly
- ❌ Lack of proactive communication about known issues (login, nominee updates)

**For Support/Product Teams:**
- ❌ Manual analysis of customer reviews to identify themes
- ❌ No structured way to brief advisors about current customer sentiment
- ❌ Scattered MCP actions (calendar, email, notes) without unified approval workflow
- ❌ Repetitive fee explanation creation

**For Advisors:**
- ❌ No context about customer sentiment before meetings
- ❌ Manual scheduling and booking management
- ❌ No linkage between what customers are asking about and what advisors should prepare for

---

## 3. CUSTOMER JOURNEY

**Current State (Fragmented):**
```
Investor → Searches multiple websites → Calls support → Gets generic answer → Manually books advisor → Advisor unprepared
```

**Desired State (Unified):**
```
Investor → Smart-Sync FAQ (M1+M2) → Voice Agent (M3, theme-aware) 
        → Calendar hold + advisor briefed with market context (M2+M3)
        → Compliant, structured booking with follow-up email
```

**Three Interconnected Flows:**

| Phase | Component | Input | Output |
|-------|-----------|-------|--------|
| **Discover** | Smart-Sync FAQ | Complex question combining facts + fees | Unified answer with sources + context |
| **Schedule** | Voice Agent (Theme-Aware) | Voice call | Booking code + calendar hold + advisor email with market sentiment |
| **Brief** | Weekly Pulse (Human-in-Loop) | Review CSV | Approved pulse + fee explainer + advisor context |

---

## 4. WHAT WE'RE SOLVING

### **Pillar A: Smart-Sync Knowledge Base** (M1 + M2)
- **Problem:** Users can't ask questions that span facts (exit load %) AND experience (why I was charged)
- **Solution:** Merge RAG FAQ with Weekly Pulse to create unified search
- **Success Metric:** One answer addresses both factsheet info + customer sentiment

### **Pillar B: Insight-Driven Agent Optimization** (M2 + M3)
- **Problem:** Voice agents are generic; advisors get no context about customer pain points
- **Solution:** Make Voice Agent "theme-aware" — proactively mention top issues identified in reviews
- **Success Metric:** Voice agent mentions relevant theme in greeting (e.g., *"I see many users have had login issues..."*)

### **Pillar C: Super-Agent MCP Workflow** (M2 + M3)
- **Problem:** Calendar holds, email drafts, and notes are disconnected; advisors lack market context
- **Solution:** Consolidate all MCP actions into one HITL approval center; include market sentiment in advisor email
- **Success Metric:** Advisor email includes Market Context snippet from Weekly Pulse

---

## 5. SOLUTION PRIORITIZATION

| Priority | Solution | Effort | Impact | Reasoning |
|----------|----------|--------|--------|-----------|
| **P0** | **Smart-Sync FAQ** (M1+M2) | High | High | Addresses core investor pain point; unifies fragmented information |
| **P0** | **Theme-Aware Voice Agent** (M2+M3) | Medium | High | Proactive context dramatically improves advisor efficiency & customer experience |
| **P1** | **Unified HITL Approval Center** (M2+M3) | Medium | Medium | Reduces manual steps; ensures compliance; links booking to customer sentiment |
| **P2** | **Evaluation Suite** (RAG + Safety + UX) | Medium | Medium | De-risks deployment; proves system works before production |
| **P3** | **State Persistence** (Booking Code visibility) | Low | Low | Nice-to-have; shows system connectivity but not critical |

---

## 6. KEY CONSTRAINTS

- ✅ **Single entry point** — One UI (Streamlit/Gradio)
- ✅ **No PII** — Mask all sensitive data (`[REDACTED]`)
- ✅ **No investment advice** — Refuse + redirect to educational links 100% of the time
- ✅ **Approval-gated MCP** — No auto-execution; human must confirm
- ✅ **Citations mandatory** — Every answer must cite official sources

---

## 7. SUCCESS METRICS

| Metric | Target | Test Type |
|--------|--------|-----------|
| **Faithfulness** | 100% | RAG Eval (doesn't hallucinate outside sources) |
| **Relevance** | 5/5 complex Q&As answered correctly | RAG Eval |
| **Safety** | 3/3 adversarial prompts refused | Safety Eval |
| **Structure** | Pulse ≤250 words + 3 actions | UX Eval |
| **Theme Awareness** | Voice agent mentions top theme from pulse | Logic Check |

---

## 8. PRODUCT ARCHITECTURE OVERVIEW

The Investor Ops & Intelligence Suite integrates three AI milestones into one unified dashboard:

```
┌─────────────────────────────────────────────────────────────┐
│          INVESTOR OPS & INTELLIGENCE SUITE                  │
│                  (Single Entry Point)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────┐ │
│  │  Pillar A        │  │  Pillar B        │  │ Pillar C │ │
│  │ Smart-Sync FAQ   │  │ Theme-Aware      │  │ HITL     │ │
│  │ (M1 + M2)        │  │ Voice Agent      │  │ Approval │ │
│  │                  │  │ (M2 + M3)        │  │ Center   │ │
│  │ • Unified Search │  │                  │  │ (M2+M3)  │ │
│  │ • Citations      │  │ • Context-Aware  │  │          │ │
│  │ • Fee Context    │  │ • Topic Briefing │  │ • Review │ │
│  │                  │  │ • Sentiment Cues │  │ • Approve│ │
│  └──────────────────┘  └──────────────────┘  └──────────┘ │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Data Layer: Reviews CSV → Weekly Pulse → Themes           │
│  Booking Layer: Voice Call → Calendar + Email + Notes      │
│  Safety Layer: RAG Eval + Adversarial Tests + UX Checks    │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. TECHNICAL IMPLEMENTATION ROADMAP

### **Phase 1: Smart-Sync FAQ (Week 1-2)**
- Integrate M1 RAG FAQ + M2 Fee Explainer
- Build unified search UI
- Add source citations
- Test with 5 complex questions

### **Phase 2: Theme-Aware Voice Agent (Week 2-3)**
- Fetch top 3 themes from Weekly Pulse
- Add theme context to voice greeting
- Generate booking code
- Create calendar hold + email draft (approval-gated)

### **Phase 3: HITL Approval Center (Week 3-4)**
- Consolidate MCP actions (calendar, email, notes)
- Add market context snippet to advisor email
- Build approval UI
- Link booking code to customer sentiment

### **Phase 4: Evaluation & Safety (Week 4)**
- Golden dataset with 5 complex Q&As
- Adversarial tests (3 scenarios)
- UX/structure validation
- Document all scores

---

## 10. SUCCESS DEFINITION

**This suite is successful when:**
1. ✅ A retail investor gets a unified answer combining facts + sentiment in one query
2. ✅ An advisor receives a voice call with proactive context about customer pain points
3. ✅ A booking is created with approval, calendar hold, email draft, and market context — all linked
4. ✅ The system refuses 100% of investment advice requests and PII attempts
5. ✅ All three milestones are visible in one dashboard

---

This integrated product transforms isolated AI prototypes into one **operational intelligence engine** that improves investor experience, empowers advisors, and gives product teams real-time customer insights.
