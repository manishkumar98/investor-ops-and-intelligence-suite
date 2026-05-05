# Source Manifest — INDMoney Investor Ops & Intelligence Suite
# Format: mf_faq: <URL>  — ingested into mf_faq_corpus (FAQ / factsheet questions)
#         fee:    <URL>  — ingested into fee_corpus (exit load / expense ratio questions)
# Lines starting with # are ignored.
# Last verified: 2026-05-05
#
# Coverage: 12 SBI Mutual Fund schemes + AMFI education + SEBI regulatory
# Local raw files: data/raw/*.txt (read by ingest_local_files() — always runs first)
# Live scrape URLs below supplement local files with fresher data where reachable.
# Total unique URLs: 42

# ── SBI Mutual Fund — Official Scheme Pages (working URLs) ───────────────────
# Focused, Liquid, Contra, Technology, Healthcare, Equity Hybrid, Magnum Global
# scheme pages return 404 — covered by data/raw/*_official.txt + Groww URLs below.

mf_faq: https://www.sbimf.com/sbimf-scheme-details/sbi-large-cap-fund-(formerly-known-as-sbi-bluechip-fund)-43
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-Flexicap-Fund-39
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-ELSS-Tax-Saver-Fund-(formerly-known-as-SBI-Long-Term-Equity-Fund)-3
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-Small-Cap-Fund-329
mf_faq: https://www.sbimf.com/sbimf-scheme-details/SBI-Midcap-Fund-34

# ── Groww — All 12 SBI Fund Detail Pages (alternative to sbimf / INDMoney) ───
# Used as live-scrape alternative for funds whose sbimf.com pages return 404
# and INDMoney pages return 403.

mf_faq: https://groww.in/mutual-funds/sbi-bluechip-fund-direct-plan-growth
mf_faq: https://groww.in/mutual-funds/sbi-flexicap-fund-direct-growth
mf_faq: https://groww.in/mutual-funds/sbi-long-term-equity-fund-direct-growth
mf_faq: https://groww.in/mutual-funds/sbi-small-cap-fund-direct-plan-growth
mf_faq: https://groww.in/mutual-funds/sbi-magnum-midcap-fund-direct-growth
mf_faq: https://groww.in/mutual-funds/sbi-focused-equity-fund-direct-growth
mf_faq: https://groww.in/mutual-funds/sbi-liquid-fund-direct-plan-growth
mf_faq: https://groww.in/mutual-funds/sbi-contra-fund-direct-plan-growth
mf_faq: https://groww.in/mutual-funds/sbi-technology-opportunities-fund-direct-growth
mf_faq: https://groww.in/mutual-funds/sbi-healthcare-opportunities-fund-direct-growth
mf_faq: https://groww.in/mutual-funds/sbi-equity-hybrid-fund-direct-growth
mf_faq: https://groww.in/mutual-funds/sbi-magnum-global-fund-direct-growth

# ── INDMoney — Fund Detail Pages (reliably reachable subset) ─────────────────
# Several INDMoney fund pages return 403 intermittently.
# All 12 funds covered by data/raw/*_indmoney.txt as fallback.

mf_faq: https://www.indmoney.com/mutual-funds/sbi-flexicap-fund-direct-growth-3249
mf_faq: https://www.indmoney.com/mutual-funds/sbi-long-term-equity-fund-direct-growth-2754
mf_faq: https://www.indmoney.com/mutual-funds/sbi-midcap-fund-direct-growth-3129
mf_faq: https://www.indmoney.com/mutual-funds/sbi-focused-equity-fund-direct-growth-3532
mf_faq: https://www.indmoney.com/mutual-funds/sbi-technology-opportunities-fund-direct-growth-4769
mf_faq: https://www.indmoney.com/mutual-funds/sbi-equity-hybrid-fund-direct-growth-2755
mf_faq: https://www.indmoney.com/mutual-funds/sbi-magnum-global-fund-direct-growth-2803

# ── AMFI — Investor Education & NAV ──────────────────────────────────────────
# /investor-corner/knowledge-center/* sub-pages return 404.
# Education content (SIP, ELSS, expense ratio, what are MFs) covered by
# data/raw/amfi_investor_education.txt

mf_faq: https://www.amfiindia.com/net-asset-value
mf_faq: https://www.amfiindia.com/investor-corner/knowledge-center.html
mf_faq: https://groww.in/p/mutual-funds/what-is-sip
mf_faq: https://groww.in/p/mutual-funds/elss-funds
mf_faq: https://groww.in/p/mutual-funds/expense-ratio

# ── SEBI — Regulatory Reference ──────────────────────────────────────────────
# Specific investor-education subpages return 404.
# Regulatory content covered by data/raw/sebi_investor_rights.txt

mf_faq: https://www.sebi.gov.in/investors.html

# ── MFCentral — Statement & Redemption ───────────────────────────────────────

mf_faq: https://www.mfcentral.com

# ── CAMS — Capital Gains & Consolidated Statement ────────────────────────────
# camsonline.com returns 500 errors on specific pages.
# CAMS statement content covered by data/raw/capital_gains_statements_(official).txt
# Groww's capital gains guide as live alternative:

mf_faq: https://groww.in/p/tax/capital-gains-statement-mutual-funds

# ── Fee Corpus — Exit Load + Expense Ratio Detail ────────────────────────────

fee: https://www.sbimf.com/sbimf-scheme-details/SBI-ELSS-Tax-Saver-Fund-(formerly-known-as-SBI-Long-Term-Equity-Fund)-3
fee: https://www.sbimf.com/sbimf-scheme-details/sbi-large-cap-fund-(formerly-known-as-sbi-bluechip-fund)-43
fee: https://www.sbimf.com/sbimf-scheme-details/SBI-Small-Cap-Fund-329
fee: https://www.sbimf.com/sbimf-scheme-details/SBI-Flexicap-Fund-39
fee: https://www.sbimf.com/sbimf-scheme-details/SBI-Midcap-Fund-34
fee: https://groww.in/mutual-funds/sbi-focused-equity-fund-direct-growth
fee: https://groww.in/mutual-funds/sbi-liquid-fund-direct-plan-growth
fee: https://groww.in/mutual-funds/sbi-contra-fund-direct-plan-growth
fee: https://groww.in/mutual-funds/sbi-technology-opportunities-fund-direct-growth
fee: https://groww.in/mutual-funds/sbi-healthcare-opportunities-fund-direct-growth
fee: https://groww.in/mutual-funds/sbi-equity-hybrid-fund-direct-growth
fee: https://groww.in/mutual-funds/sbi-magnum-global-fund-direct-growth
fee: https://www.amfiindia.com/investor-corner/knowledge-center.html
