"""Per-fund priority URL map for the Knowledge Base sync.

For each canonical fund name:
  - urls: ordered list of 3 URLs to try; first that returns content is used
  - mfapi_code: AMFI scheme code used as last-resort fallback via api.mfapi.in

Priority order is: groww.in → indmoney.com → sbimf.com (or as specified per fund).
If all 3 fail, live NAV data is fetched from api.mfapi.in/{mfapi_code}.
"""

FUND_PRIORITY_URLS: dict[str, dict] = {
    "SBI Large Cap Fund": {
        "urls": [
            "https://groww.in/mutual-funds/sbi-large-cap-direct-plan-growth",
            "https://www.indmoney.com/mutual-funds/sbi-large-cap-fund-direct-growth-3046",
            "https://www.sbimf.com/sbimf-scheme-details/sbi-large-cap-fund-(formerly-known-as-sbi-bluechip-fund)-43",
        ],
        "mfapi_code": 119598,
    },
    "SBI Flexicap Fund": {
        "urls": [
            "https://groww.in/mutual-funds/sbi-flexicap-fund-direct-growth",
            "https://www.indmoney.com/mutual-funds/sbi-flexicap-fund-direct-growth-3249",
            "https://www.sbimf.com/sbimf-scheme-details/sbi-flexicap-fund-39",
        ],
        "mfapi_code": 119718,
    },
    "SBI ELSS Tax Saver Fund": {
        "urls": [
            "https://www.sbimf.com/sbimf-scheme-details/sbi-elss-tax-saver-fund-(formerly-known-as-sbi-long-term-equity-fund)-3",
            "https://groww.in/mutual-funds/sbi-elss-tax-saver-fund-direct-growth",
            "https://www.indmoney.com/mutual-funds/sbi-elss-tax-saver-fund-direct-growth-2754",
        ],
        "mfapi_code": 119723,
    },
    "SBI Small Cap Fund": {
        "urls": [
            "https://www.sbimf.com/sbimf-scheme-details/sbi-small-cap-fund-329",
            "https://groww.in/mutual-funds/sbi-small-midcap-fund-direct-growth",
            "https://www.indmoney.com/mutual-funds/sbi-small-cap-fund-direct-plan-growth-3603",
        ],
        "mfapi_code": 125497,
    },
    "SBI Midcap Fund": {
        "urls": [
            "https://www.sbimf.com/sbimf-scheme-details/sbi-midcap-fund-34",
            "https://groww.in/mutual-funds/sbi-mid-cap-direct-plan-growth",
            "https://www.indmoney.com/mutual-funds/sbi-midcap-fund-direct-growth-3129",
        ],
        "mfapi_code": 119716,
    },
    "SBI Focused Equity Fund": {
        "urls": [
            "https://www.sbimf.com/sbimf-scheme-details/sbi-focused-fund-25",
            "https://groww.in/mutual-funds/sbi-focused-fund-direct-plan-growth",
            "https://www.indmoney.com/mutual-funds/sbi-focused-fund-direct-plan-growth-2830",
        ],
        "mfapi_code": 119727,
    },
    "SBI Liquid Fund": {
        "urls": [
            "https://www.sbimf.com/sbimf-scheme-details/sbi-liquid-fund-19",
            "https://groww.in/mutual-funds/sbi-premier-liquid-fund-direct-growth",
            "https://www.indmoney.com/mutual-funds/sbi-liquid-fund-direct-plan-growth-1247",
        ],
        "mfapi_code": 119800,
    },
    "SBI Contra Fund": {
        "urls": [
            "https://www.sbimf.com/sbimf-scheme-details/sbi-contra-fund-12",
            "https://groww.in/mutual-funds/sbi-contra-fund-direct-growth",
            "https://www.indmoney.com/mutual-funds/sbi-contra-fund-direct-growth-2612",
        ],
        "mfapi_code": 119835,
    },
    "SBI Technology Opportunities Fund": {
        "urls": [
            "https://www.sbimf.com/sbimf-scheme-details/sbi-technology-opportunities-fund-10",
            "https://groww.in/mutual-funds/sbi-it-fund-direct-growth",
            "https://www.indmoney.com/mutual-funds/sbi-technology-opportunities-fund-direct-growth-3469",
        ],
        "mfapi_code": 120578,
    },
    "SBI Healthcare Opportunities Fund": {
        "urls": [
            "https://www.sbimf.com/sbimf-scheme-details/sbi-healthcare-opportunities-fund-11",
            "https://groww.in/mutual-funds/sbi-pharma-fund-direct-growth",
            "https://www.indmoney.com/mutual-funds/sbi-healthcare-opportunities-fund-direct-growth-3446",
        ],
        "mfapi_code": 119783,
    },
    "SBI Equity Hybrid Fund": {
        "urls": [
            "https://www.sbimf.com/sbimf-scheme-details/sbi-equity-hybrid-fund-5",
            "https://groww.in/mutual-funds/sbi-magnum-balanced-fund-direct-growth",
            "https://www.indmoney.com/mutual-funds/sbi-equity-hybrid-fund-direct-growth-4170",
        ],
        "mfapi_code": 119609,
    },
    "SBI MNC Fund": {
        "urls": [
            "https://www.sbimf.com/sbimf-scheme-details/sbi-mnc-fund-(formerly-known-as-sbi-magnum-global-fund)-4",
            "https://groww.in/mutual-funds/sbi-mnc-direct-plan-growth",
            "https://www.indmoney.com/mutual-funds/sbi-mnc-fund-direct-growth-3462",
        ],
        "mfapi_code": 120575,
        "former_names": ["SBI Magnum Global Fund"],
    },
}
