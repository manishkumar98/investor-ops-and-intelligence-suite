"""
AI Evals Runner — Investor Ops Voice Agent (Dalal Street Advisors)

Runs all 5 eval suites:
  1. Intent Classification  — accuracy across 10 intent types (45 cases)
  2. Slot Extraction        — precision/recall/F1 per slot (20 cases)
  3. Compliance             — safety recall for advice + PII flags (20 cases)
  4. Conversation Flows     — multi-turn FSM correctness, mocked MCP (10 flows)
  5. LLM Judge              — Claude scores agent response quality (8 samples)

Usage:
  python phase4_voice_pillar_b/evals/run_evals.py
  python phase4_voice_pillar_b/evals/run_evals.py --offline
  python phase4_voice_pillar_b/evals/run_evals.py --only intent
  python phase4_voice_pillar_b/evals/run_evals.py --only slots
  python phase4_voice_pillar_b/evals/run_evals.py --only compliance
  python phase4_voice_pillar_b/evals/run_evals.py --only flows
  python phase4_voice_pillar_b/evals/run_evals.py --only judge
  python phase4_voice_pillar_b/evals/run_evals.py --no-judge

Baselines (from voice-agents reference implementation):
  Intent Accuracy:   68.9%
  Slot Full-Match:   85.0%
  Compliance:        83.3%
  Flow Pass Rate:    90.0%

Results saved to: phase4_voice_pillar_b/evals/results/eval_results_<timestamp>.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def _pct(val: float) -> str:
    return f"{val * 100:.1f}%"


def _bar(val: float, width: int = 20) -> str:
    filled = int(val * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def _color(val: float, good: float = 0.8, warn: float = 0.6) -> str:
    if val >= good:
        return GREEN
    elif val >= warn:
        return YELLOW
    return RED


def print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 60}{RESET}")


def print_intent_summary(r: dict):
    acc = r["accuracy"]
    c = _color(acc)
    print(f"\n  Overall Accuracy: {c}{BOLD}{_pct(acc)}{RESET}  {_bar(acc)}  ({r['correct']}/{r['total']})")
    print(f"\n  {'Category':<30} {'Accuracy':>10}  {'Count':>8}")
    print(f"  {'─'*50}")
    for cat, m in sorted(r["category_accuracy"].items()):
        cc = _color(m["accuracy"])
        print(f"  {cat:<30} {cc}{_pct(m['accuracy']):>10}{RESET}  {m['correct']}/{m['total']:>3}")
    if r["failures"]:
        print(f"\n  {RED}Failures ({len(r['failures'])}):{RESET}")
        for f in r["failures"][:5]:
            print(f"    [{f['id']}] \"{f['input'][:50]}\"  expected={f['expected']}  got={f['predicted']}")


def print_slot_summary(r: dict):
    fmr = r["full_match_rate"]
    c = _color(fmr)
    print(f"\n  Full Match Rate: {c}{BOLD}{_pct(fmr)}{RESET}  ({r['full_match_count']}/{r['total']})")
    print(f"\n  {'Slot':<30} {'F1':>6}  {'Precision':>10}  {'Recall':>8}")
    print(f"  {'─'*58}")
    for slot, m in r["slot_metrics"].items():
        sc = _color(m["f1"])
        print(f"  {slot:<30} {sc}{m['f1']:>6.3f}{RESET}  {m['precision']:>10.3f}  {m['recall']:>8.3f}")


def print_compliance_summary(r: dict):
    acc = r["accuracy"]
    c = _color(acc)
    print(f"\n  Overall Accuracy: {c}{BOLD}{_pct(acc)}{RESET}  ({r['correct']}/{r['total']})")
    sfn = r["safety_false_negatives"]
    sfn_color = RED if sfn > 0 else GREEN
    print(f"\n  Safety False Negatives (advice/PII missed): {sfn_color}{BOLD}{sfn}{RESET}")
    for flag, recall in r["safety_recall"].items():
        rc = _color(recall, good=1.0, warn=0.9)
        print(f"    {flag} recall: {rc}{_pct(recall)}{RESET}")
    print(f"\n  {'Flag':<20} {'F1':>6}  {'Precision':>10}  {'Recall':>8}")
    print(f"  {'─'*48}")
    for flag, m in r["flag_metrics"].items():
        sc = _color(m["f1"])
        print(f"  {str(flag):<20} {sc}{m['f1']:>6.3f}{RESET}  {m['precision']:>10.3f}  {m['recall']:>8.3f}")


def print_flow_summary(r: dict):
    pr = r["pass_rate"]
    c = _color(pr)
    print(f"\n  Pass Rate: {c}{BOLD}{_pct(pr)}{RESET}  ({r['passed']}/{r['total']})")
    for result in r["results"]:
        icon = f"{GREEN}✓{RESET}" if result.get("passed") else f"{RED}✗{RESET}"
        print(f"    {icon} [{result['id']}] {result['description']}")
        if not result.get("passed"):
            if result.get("error"):
                print(f"       {RED}Error: {result['error']}{RESET}")
            else:
                for t in result.get("turns", []):
                    if not t.get("state_match"):
                        print(f"       {RED}Turn: \"{t['user'][:40]}\"  expected={t['expected_state']}  got={t['actual_state']}{RESET}")


def print_judge_summary(r: dict):
    if "error" in r:
        print(f"\n  {YELLOW}Skipped: {r['error']}{RESET}")
        return
    print(f"\n  Evaluated: {r['evaluated']}/{r['total']} responses")
    print(f"  Avg Tone:        {_color(r['avg_tone']/5)}{r['avg_tone']:.2f}/5{RESET}")
    print(f"  Avg Clarity:     {_color(r['avg_clarity']/5)}{r['avg_clarity']:.2f}/5{RESET}")
    print(f"  Avg Helpfulness: {_color(r['avg_helpfulness']/5)}{r['avg_helpfulness']:.2f}/5{RESET}")
    cpr = r["compliance_pass_rate"]
    print(f"  Compliance Pass: {_color(cpr, good=1.0, warn=0.9)}{_pct(cpr)}{RESET}")
    if r.get("low_score_responses"):
        print(f"\n  {RED}Low scoring responses:{RESET}")
        for lr in r["low_score_responses"]:
            print(f"    [{lr['id']}] {lr['category']}: overall={lr['scores'].get('overall_score', '?')}")


def main():
    parser = argparse.ArgumentParser(description="Run AI evals for the Investor Ops Voice Agent")
    parser.add_argument("--offline", action="store_true", help="Rule-based only (no LLM APIs)")
    parser.add_argument("--only", choices=["intent", "slots", "compliance", "flows", "judge"],
                        help="Run only one eval suite")
    parser.add_argument("--no-judge", action="store_true", help="Skip LLM judge eval")
    args = parser.parse_args()

    use_llm = not args.offline
    run_all = args.only is None

    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  Dalal Street Advisors — AI Evals Suite{RESET}")
    print(f"  Mode: {'Rule-based (offline)' if args.offline else 'LLM (Groq/Claude)'}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{BOLD}{'═' * 60}{RESET}")

    _EVALS_DIR = Path(__file__).parent
    sys.path.insert(0, str(_EVALS_DIR))

    all_results = {}
    t_start = time.monotonic()

    if run_all or args.only == "intent":
        print_header("1/5  Intent Classification  (45 cases, 10 intent types)")
        from evaluators.intent_eval import run_intent_eval
        t0 = time.monotonic()
        r = run_intent_eval(use_llm=use_llm)
        r["elapsed_s"] = round(time.monotonic() - t0, 1)
        print_intent_summary(r)
        print(f"\n  Elapsed: {r['elapsed_s']}s")
        all_results["intent_classification"] = r

    if run_all or args.only == "slots":
        print_header("2/5  Slot Extraction  (20 cases)")
        from evaluators.slot_eval import run_slot_eval
        t0 = time.monotonic()
        r = run_slot_eval(use_llm=use_llm)
        r["elapsed_s"] = round(time.monotonic() - t0, 1)
        print_slot_summary(r)
        print(f"\n  Elapsed: {r['elapsed_s']}s")
        all_results["slot_extraction"] = r

    if run_all or args.only == "compliance":
        print_header("3/5  Compliance / Safety  (20 cases: 12 must-block + 5 clean)")
        from evaluators.compliance_eval import run_compliance_eval
        t0 = time.monotonic()
        r = run_compliance_eval(use_llm=use_llm)
        r["elapsed_s"] = round(time.monotonic() - t0, 1)
        print_compliance_summary(r)
        print(f"\n  Elapsed: {r['elapsed_s']}s")
        all_results["compliance"] = r

    if run_all or args.only == "flows":
        print_header("4/5  Conversation Flows  (10 multi-turn flows, mocked MCP)")
        from evaluators.conversation_eval import run_conversation_eval
        t0 = time.monotonic()
        r = run_conversation_eval(use_llm=use_llm)
        r["elapsed_s"] = round(time.monotonic() - t0, 1)
        print_flow_summary(r)
        print(f"\n  Elapsed: {r['elapsed_s']}s")
        all_results["conversation_flows"] = r

    if (run_all or args.only == "judge") and not args.no_judge:
        print_header("5/5  LLM-as-Judge Response Quality  (8 samples, Claude haiku)")
        from evaluators.llm_judge import run_llm_judge_eval
        t0 = time.monotonic()
        r = run_llm_judge_eval()
        r["elapsed_s"] = round(time.monotonic() - t0, 1)
        print_judge_summary(r)
        print(f"\n  Elapsed: {r['elapsed_s']}s")
        all_results["llm_judge"] = r

    total_elapsed = round(time.monotonic() - t_start, 1)
    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  SUMMARY{RESET}")
    print(f"  Total elapsed: {total_elapsed}s")
    print()

    score_map = {
        "intent_classification": ("accuracy",       "Intent Accuracy     (baseline 68.9%)"),
        "slot_extraction":       ("full_match_rate", "Slot Full-Match     (baseline 85.0%)"),
        "compliance":            ("accuracy",        "Compliance Accuracy (baseline 83.3%)"),
        "conversation_flows":    ("pass_rate",       "Flow Pass Rate      (baseline 90.0%)"),
    }
    overall_scores = []
    for key, (metric, label) in score_map.items():
        if key in all_results:
            val = all_results[key].get(metric, 0)
            c = _color(val)
            overall_scores.append(val)
            print(f"  {label:<45} {c}{BOLD}{_pct(val)}{RESET}  {_bar(val, 12)}")

    if overall_scores:
        avg = sum(overall_scores) / len(overall_scores)
        c = _color(avg)
        print(f"\n  {'Overall Score':<45} {c}{BOLD}{_pct(avg)}{RESET}  {_bar(avg, 12)}")

    print(f"{BOLD}{'═' * 60}{RESET}\n")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"eval_results_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(
            {"timestamp": ts, "mode": "offline" if args.offline else "llm", "results": all_results},
            f, indent=2, default=str,
        )
    print(f"  Results saved → {out_path}\n")

    if overall_scores and min(overall_scores) < 0.7:
        sys.exit(1)


if __name__ == "__main__":
    main()
