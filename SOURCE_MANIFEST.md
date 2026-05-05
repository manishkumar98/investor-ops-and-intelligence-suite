# Source Manifest — Investor Ops & Intelligence Suite by Dalal Street Advisors
# Format: mf_faq: <URL>  — ingested into mf_faq_corpus (FAQ / factsheet questions)
#         fee:    <URL>  — ingested into fee_corpus (exit load / expense ratio questions)
# Lines starting with # are ignored.
# Last verified: 2026-05-05
#
# Coverage: 12 SBI Mutual Fund schemes, official AMC + INDMoney pages, AMFI, SEBI, CAMS, MFCentral
# Total unique URLs: 50

# ── SBI Mutual Fund — Official Scheme Pages (sbimf.com) ─────────────────────
# Source for: expense ratio, exit load, lock-in, riskometer, benchmark, min SIP

mf_faq: https://www.sbimf.com/sbimf-scheme-details/sbi-large-cap-fund-(formerly-known-as-sbi-bluechip-fund)-43
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-Flexicap-Fund-39
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-ELSS-Tax-Saver-Fund-(formerly-known-as-SBI-Long-Term-Equity-Fund)-3
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-Small-Cap-Fund-329
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-Midcap-Fund-34
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-Focused-Equity-Fund-37
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-Liquid-Fund-42
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-Contra-Fund-33
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-Technology-Opportunities-Fund-48
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-Healthcare-Opportunities-Fund-36
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-Equity-Hybrid-Fund-35
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-Magnum-Global-Fund-44

# ── SBI Mutual Fund — Investor Service Pages ─────────────────────────────────

mf_faq: https://www.sbimf.com/en-us/sip-calculator
mf_faq: https://www.sbimf.com/en-us/investor-service/exit-load
mf_faq: https://www.sbimf.com/en-us/investor-service/expense-ratio

# ── INDMoney — Fund Detail Pages (8 funds, direct-growth) ────────────────────
# Source for: current NAV, fund performance, holdings breakdown on INDMoney platform

mf_faq: https://www.indmoney.com/mutual-funds/sbi-bluechip-fund-direct-growth-3046
mf_faq: https://www.indmoney.com/mutual-funds/sbi-flexicap-fund-direct-growth-3249
mf_faq: https://www.indmoney.com/mutual-funds/sbi-long-term-equity-fund-direct-growth-2754
mf_faq: https://www.indmoney.com/mutual-funds/sbi-small-cap-fund-direct-plan-growth-3603
mf_faq: https://www.indmoney.com/mutual-funds/sbi-midcap-fund-direct-growth-3129
mf_faq: https://www.indmoney.com/mutual-funds/sbi-focused-equity-fund-direct-growth-3532
mf_faq: https://www.indmoney.com/mutual-funds/sbi-liquid-fund-direct-growth-2831
mf_faq: https://www.indmoney.com/mutual-funds/sbi-contra-fund-direct-growth-3081
mf_faq: https://www.indmoney.com/mutual-funds/sbi-technology-opportunities-fund-direct-growth-4769
mf_faq: https://www.indmoney.com/mutual-funds/sbi-healthcare-opportunities-fund-direct-growth-2768
mf_faq: https://www.indmoney.com/mutual-funds/sbi-equity-hybrid-fund-direct-growth-2755
mf_faq: https://www.indmoney.com/mutual-funds/sbi-magnum-global-fund-direct-growth-2803
mf_faq: https://www.indmoney.com/mutual-funds/amc/sbi-mutual-fund

# ── AMFI — Investor Education & NAV ──────────────────────────────────────────
# Source for: expense ratio explanation, SIP mechanics, ELSS definition, NAV lookup

mf_faq: https://www.amfiindia.com/investor-corner/knowledge-center/expense-ratio.html
mf_faq: https://www.amfiindia.com/investor-corner/knowledge-center/what-are-mutual-funds.html
mf_faq: https://www.amfiindia.com/investor-corner/knowledge-center/sip.html
mf_faq: https://www.amfiindia.com/investor-corner/knowledge-center/elss.html
mf_faq: https://www.amfiindia.com/net-asset-value

# ── SEBI — Regulatory Reference ──────────────────────────────────────────────
# Source for: investor rights, MF regulatory framework, compliance disclaimers

mf_faq: https://www.sebi.gov.in/investors.html
mf_faq: https://www.sebi.gov.in/investor-education/financial-products/mutual-funds.html

# ── CAMS + MFCentral — Statement & Redemption ────────────────────────────────
# Source for: capital gains statement download, consolidated account statement

mf_faq: https://www.camsonline.com/Investors/Statements/Capital-Gains-Statement
mf_faq: https://www.camsonline.com/Investors/Statements/Consolidated-Account-Statement
mf_faq: https://www.mfcentral.com

# ── Fee Corpus — SBI Scheme Pages (exit load + expense ratio detail) ─────────
# Dual-ingested: also in mf_faq above; fee: prefix loads into fee_corpus

fee: https://www.sbimf.com/sbimf-scheme-details/SBI-ELSS-Tax-Saver-Fund-(formerly-known-as-SBI-Long-Term-Equity-Fund)-3
fee: https://www.sbimf.com/sbimf-scheme-details/sbi-large-cap-fund-(formerly-known-as-sbi-bluechip-fund)-43
fee: https://www.sbimf.com/sbimf-scheme-details/SBI-Small-Cap-Fund-329
fee: https://www.sbimf.com/sbimf-scheme-details/SBI-Flexicap-Fund-39
fee: https://www.sbimf.com/sbimf-scheme-details/SBI-Midcap-Fund-34
fee: https://www.sbimf.com/sbimf-scheme-details/SBI-Focused-Equity-Fund-37
fee: https://www.sbimf.com/sbimf-scheme-details/SBI-Liquid-Fund-42
fee: https://www.sbimf.com/sbimf-scheme-details/SBI-Contra-Fund-33
fee: https://www.sbimf.com/sbimf-scheme-details/SBI-Technology-Opportunities-Fund-48
fee: https://www.sbimf.com/sbimf-scheme-details/SBI-Healthcare-Opportunities-Fund-36
fee: https://www.sbimf.com/sbimf-scheme-details/SBI-Equity-Hybrid-Fund-35
fee: https://www.sbimf.com/sbimf-scheme-details/SBI-Magnum-Global-Fund-44
fee: https://www.sbimf.com/en-us/investor-service/exit-load
fee: https://www.sbimf.com/en-us/investor-service/expense-ratio
fee: https://www.amfiindia.com/investor-corner/knowledge-center/expense-ratio.html
fee: https://www.indmoney.com/mutual-funds/sbi-small-cap-fund-direct-plan-growth-3603
