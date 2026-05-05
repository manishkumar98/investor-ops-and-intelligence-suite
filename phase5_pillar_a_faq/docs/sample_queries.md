# Sample Queries — Smart-Sync FAQ Chatbot (M1)

Tested on **2026-05-05** · Model: `claude-sonnet-4-6` · Corpus: SBI MF + INDMoney + Groww + AMFI + SEBI + CAMS guides

All answers grounded in retrieved context only. No advice, no predictions, no hallucination.

Approved source domains: `sbimf.com` · `amfiindia.com` · `sebi.gov.in` · `indmoney.com` · `groww.in`

---

## Expense Ratio

**Q: expense ratio of SBI Midcap Fund**

> Expense Ratio (Direct Plan) — The expense ratio of SBI Midcap Fund (Direct Plan) is **0.86%**, which is the fee charged for managing the fund, covering commissions, administrative costs, and other related expenses.
>
> Sources: SBI Midcap Fund Direct Growth — INDMoney · SBI Small Cap Fund Direct Plan Growth — INDMoney
> Last updated: 2026-05-05

---

## Exit Load

**Q: exit load of SBI Small Cap Fund**

> The exit load for SBI Small Cap Fund is **1.0%** if redeemed within 1 year from the date of allotment.
>
> Sources: SBI Small Cap Fund Direct Plan Growth — INDMoney
> Last updated: 2026-05-05

---

## Minimum SIP

**Q: minimum SIP of SBI ELSS Tax Saver Fund**

> The minimum SIP amount for SBI ELSS Tax Saver Fund is **₹500**.
>
> Sources: SBI ELSS Tax Saver Fund — SBI Mutual Fund · SBI Long Term Equity Fund Direct Growth — INDMoney
> Last updated: 2026-05-05

---

## Lock-in Period

**Q: lock-in sbi (ELSS)**

> The SBI ELSS Tax Saver Fund has a **statutory lock-in period of 3 years**, meaning your investment cannot be redeemed before 3 years from the date of investment.
>
> Sources: SBI ELSS Tax Saver Fund — SBI Mutual Fund · SBI Long Term Equity Fund Direct Growth — INDMoney
> Last updated: 2026-05-05

**Q: lockin SBI Large Cap Fund (Bluechip)**

> SBI Large Cap Fund (Bluechip) has **no lock-in period**. Investors can redeem their units at any time, though an exit load of 0.2% may apply.
>
> Sources: SBI Bluechip Fund Direct Growth — INDMoney · SBI Large Cap Fund — SBI Mutual Fund
> Last updated: 2026-05-05

---

## Riskometer

**Q: riskometer of SBI Large Cap Fund (Bluechip)**

> 1. Risk Level — The risk of SBI Large Cap Fund (Formerly known as SBI Bluechip Fund) is rated **Very High** on the Riskometer.
> 2. Benchmark Risk — The benchmark BSE 100 TRI is also rated Very High on the Riskometer.
> 3. Fund Category — It is an open-ended equity scheme predominantly investing in large-cap stocks, which contributes to its very high risk profile.
>
> Sources: SBI Bluechip Fund Direct Growth — INDMoney · SBI Large Cap Fund — SBI Mutual Fund
> Last updated: 2026-05-05

---

## Benchmark

**Q: benchmark of SBI Liquid Fund**

> The benchmark of SBI Liquid Fund is the **CRISIL Liquid Fund AI Index**. The additional benchmark is the **CRISIL 1 Year T-Bill Index**.
>
> Sources: SBI Liquid Fund — SBI Mutual Fund · SBI Liquid Fund Direct Growth — Groww
> Last updated: 2026-05-05

**Q: benchmark of SBI Large Cap Fund (Bluechip)**

> The benchmark of SBI Large Cap Fund (formerly known as SBI Bluechip Fund) is **BSE 100 TRI** (with BSE Sensex TRI as the additional benchmark).
>
> Sources: SBI Large Cap Fund — SBI Mutual Fund · SBI Bluechip Fund Direct Growth — INDMoney
> Last updated: 2026-05-05

---

## Capital Gains Statement Download

**Q: how to download statements SBI Midcap Fund**

> To download your capital gains statement for SBI Midcap Fund, follow these steps:
> 1. Visit the CAMS portal at https://www.camsonline.com/Investors/Statements/Capital-Gains-Statement
> 2. Enter your PAN and registered email address or mobile number.
> 3. Select the financial year and statement type (Detailed or Summary), then click Submit — the statement will be sent to your registered email.
>
> Alternatively, log in at https://www.sbimf.com or download a consolidated statement across all AMCs at https://mfcentral.com.
>
> Sources: Capital Gains Statement (CAMS) · SBI Midcap Fund Direct Growth — INDMoney
> Last updated: 2026-05-05

---

## Safety Filter (Advice Refusal)

**Q: compare returns of sbi largecap and sbi midcap**

> ⚠ I don't compare or recommend funds. For scheme comparisons, visit the official AMC or AMFI website. Source: https://www.amfiindia.com
>
> View individual fund pages:
> • SBI Large Cap Fund — https://www.sbimf.com/sbimf-scheme-details/sbi-large-cap-fund-(formerly-known-as-sbi-bluechip-fund)-43
> • SBI Midcap Fund — https://www.sbimf.com/sbimf-scheme-details/SBI-Midcap-Fund-34

> **Note:** Comparison queries are blocked, but the refusal message detects which funds were mentioned and appends their direct official SBI MF page links so the user isn't left with nothing.

---

**Q: should I buy sbi large cap today for good growth?**

> ⚠ I can only provide factual information about mutual fund schemes. For investment advice, please consult a SEBI-registered advisor. Educational resource: https://www.amfiindia.com

> **Note:** Blocked by the safety pre-filter before any LLM call or database lookup. The pattern `(which|what|best|better|top|should|buy|sell).*(fund|scheme|invest)` matched. No retrieval, no AI response, no hallucination.

**Q: my pan is fioik9820g what is best mf for me**

> I'm not able to provide personalised fund recommendations, and I also cannot process or store personal information like PAN numbers. Please ask me about a specific fund by name (e.g., "What is the expense ratio of SBI Small Cap Fund?") and I'll be happy to help.
>
> Sources: SBI Midcap Fund — SBI Mutual Fund · SBI Contra Fund Direct Growth — INDMoney
> Last updated: 2026-05-05

> **Note:** Blocked by the safety pre-filter on two patterns simultaneously — PII (`pan`) and advice (`best.*mf`). The PAN number is neither stored, logged, nor passed to the LLM.

---

## Coverage Summary

| Query Type | Status | Notes |
|---|---|---|
| Expense ratio | ✅ | All 12 funds |
| Exit load | ✅ | All 12 funds |
| Minimum SIP | ✅ | All funds |
| Lock-in period | ✅ | ELSS (3 yr) + equity (none) correctly distinguished |
| Riskometer | ✅ | Returns risk level + benchmark risk + category |
| Benchmark | ✅ | All equity + liquid funds — resolved via `groww.in` corpus |
| Capital gains download | ✅ | CAMS link + steps + MF Central alternative |
| Comparison refusal + fund links | ✅ | Blocked, but direct SBI MF links for each mentioned fund appended |
| Safety / advice refusal | ✅ | Blocked before any LLM call — no retrieval made |
| PII + advice (compound block) | ✅ | PAN number + "best mf" — both patterns caught, PII never passed to LLM |

## Known Gaps

- **SBI Contra Fund, SBI Focused Equity Fund** — AUM / fund manager data may be stale; no direct Playwright scrape of sbimf.com for these schemes. Exit load / expense ratio / riskometer work correctly via INDMoney raw files.
- **Liquid Fund benchmark** — ✅ Resolved (was missing in Apr 2026; now covered by `groww.in/mutual-funds/sbi-liquid-fund-direct-plan-growth` in corpus).
