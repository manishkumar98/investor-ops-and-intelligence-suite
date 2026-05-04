## Week of May 5, 2026

### Weekly Note
Synthesised reviews across the full period reveal a clear fault line: casual and cost-conscious users are genuinely delighted by INDMoney's low-brokerage model, while active and F&O traders are experiencing serious, money-losing failures that are driving uninstalls and low ratings. Two P0 production issues demand immediate escalation. First, a chart zoom gesture is triggering unintended order execution, directly causing user losses — a critical trading-safety bug. Second, a persistent 9:15 AM market-open detection failure has been blocking order placement for over a month, impacting traders at the most critical moment of the session. Both issues represent real financial harm and must be treated as incidents. Compounding these bugs is a brokerage billing trust crisis: users on Flash Trading plans report being charged ₹20 per F&O order despite being promised ₹10 or lower, with at least one confirmed uninstall citing competitor alternatives. Simultaneously, multiple feature gaps are limiting the platform's appeal to experienced traders: no kill switch, no limit sell order, no dual or triple chart view, no commodity segment, and no automated chart pattern detection. The ₹5-per-order brokerage remains a powerful differentiator and retention lever for cost-sensitive users, but its impact is undermined when billing is opaque or incorrect. New-user onboarding appears adequate, but the product shows significant cracks under active trading conditions.

### Top 3 Themes
- Critical order execution failures and chart interaction bugs causing real financial loss
- Brokerage overcharging versus promised rates eroding trust and driving uninstalls
- Missing table-stakes trading features blocking retention of active and F&O traders

### Action Ideas
1. Declare P0 incidents for both the chart-zoom unintended order execution bug and the 9:15 AM market-open detection failure — assign dedicated engineering squads to root-cause, hotfix, and ship user-facing status updates within the current sprint, prioritising trading-safety above all else.
2. Audit Flash Trading brokerage billing logic end-to-end and surface a real-time, itemised brokerage breakdown on the order confirmation and post-trade screens so users can verify charges match their subscribed plan, immediately rebuilding billing trust and reducing support escalations.
3. Accelerate delivery of kill switch, limit sell order, and dual or triple chart view as a bundled active-trader feature sprint, and add automated chart pattern detection push notifications to the near-term roadmap to close the feature gap driving low ratings among F&O and scalping-focused users.

---

## Week of May 4, 2026

### Weekly Note
Synthesised reviews across the full period reveal a clear fault line: casual and cost-conscious users are genuinely delighted by INDMoney's low-brokerage model, while active and F&O traders are experiencing serious, money-losing failures that are driving uninstalls and low ratings. Two P0 production issues demand immediate escalation. First, a chart zoom gesture is triggering unintended order execution, directly causing user losses — a critical trading-safety bug. Second, a persistent 9:15 AM market-open detection failure has been blocking order placement for over a month, impacting traders at the most critical moment of the session. Both issues represent real financial harm and must be treated as incidents. Compounding these bugs is a brokerage billing trust crisis: users on Flash Trading plans report being charged ₹20 per F&O order despite being promised ₹10 or lower, with at least one confirmed uninstall citing competitor alternatives. Simultaneously, multiple feature gaps are limiting the platform's appeal to experienced traders: no kill switch, no limit sell order, no dual or triple chart view, no commodity segment, and no automated chart pattern detection. The ₹5-per-order brokerage remains a powerful differentiator and retention lever for cost-sensitive users, but its impact is undermined when billing is opaque or incorrect. New-user onboarding appears adequate, but the product shows significant cracks under active trading conditions.

### Top 3 Themes
- Critical order execution failures and chart interaction bugs causing real financial loss
- Brokerage overcharging versus promised rates eroding trust and driving uninstalls
- Missing table-stakes trading features blocking retention of active and F&O traders

### Action Ideas
1. Declare P0 incidents for both the chart-zoom unintended order execution bug and the 9:15 AM market-open detection failure — assign dedicated engineering squads to root-cause, hotfix, and ship user-facing status updates within the current sprint, prioritising trading-safety above all else.
2. Audit Flash Trading brokerage billing logic end-to-end and surface a real-time, itemised brokerage breakdown on the order confirmation and post-trade screens so users can verify charges match their subscribed plan, immediately rebuilding billing trust and reducing support escalations.
3. Accelerate delivery of kill switch, limit sell order, and dual or triple chart view as a bundled active-trader feature sprint, and add automated chart pattern detection push notifications to the near-term roadmap to close the feature gap driving low ratings among F&O and scalping-focused users.

---

## Week of April 29, 2026

### Weekly Note
This week's consolidated reviews present a split picture of INDMoney's INDStocks platform — genuine strengths undercut by severe reliability failures. On the positive side, users consistently praise the intuitive interface, ₹5 flat brokerage for intraday and F&O, Flash Mode, and AI-driven market insights as meaningful differentiators against established brokers. The platform is viewed as fast-growing and well-positioned competitively. However, critical reliability issues are causing direct, quantifiable financial harm. Stop loss orders are failing to trigger or display in open positions, the 9:15 AM order rejection bug has persisted for over a month, and chart instability — including lagging candles, disappearing positions, and unintended trade executions via zoom — has resulted in user-reported losses ranging from ₹15,000 to ₹43,000. Brokerage pricing confusion is a cross-cutting trust issue, with users reporting charges of ₹20 instead of the advertised ₹5, and some alleging fraud after promotional rates were denied post-signup. Feature gaps — including absent Mutual Funds tab, commodity trading, trailing stop-loss for options, and TradingView chart integration for F&O — represent the next tier of urgency. Customer support responsiveness also drew criticism. Immediate engineering focus on crash stability and order execution integrity is essential to protect user trust before positive brand momentum is irreversibly damaged.

### Top 3 Themes
- App crashes and performance issues during live trading
- Stop loss and order execution failures
- Low brokerage charges and pricing transparency concerns

### Action Ideas
1. Immediately audit and fix stop loss trigger reliability, the 9:15 AM order rejection bug, and chart stability issues — these are causing verified financial losses and represent the highest-severity risk to user trust and retention.
2. Publish a clear, locked in-app brokerage pricing page for Flash and F&O trading that reflects advertised rates at signup, and enforce consistent application of promotional pricing across support teams to eliminate fraud perception.
3. Integrate a dedicated Mutual Funds tab within INDStocks and prioritize charting enhancements — trailing stop-loss for options, save-chart settings, and candle tools — to address the most repeated power-user and mainstream feature requests.

---

## Week of April 24, 2026

### Weekly Note
Reviews this week present a polarised but telling picture of INDmoney's trading product. On the critical side, three systemic issues dominate negative sentiment. First, app crashes and server instability during peak hours — especially at the 9:15 AM market open and intraday sessions — are directly causing measurable financial losses, with users citing losses ranging from ₹15,000 to over ₹1,00,000. Second, order execution failures including stale 'market not open' errors persisting for over a month, stop-losses not reflecting in open positions, and missing auto-exit functionality are severely eroding trader trust. Third, charting gaps in Flash Trading mode — absent TradingView integration, no dual-chart or split-chart view, disappearing indicators on relaunch — are the loudest repeated feature request from power users. Brokerage pricing discrepancies between advertised rates (₹5–₹10) and actual charges (₹20) are generating fraud accusations and driving uninstalls. Funds-not-credited complaints remain unresolved for some users across multiple months. On the positive side, Flash Mode AI insights, fast execution when stable, intuitive UI, and low brokerage pricing are building strong loyalty among intraday and options traders, with several users rating INDStock above ten competing platforms. Immediate engineering and product focus on server resilience, order reliability, chart completeness, and transparent pricing communication is critical to protecting and growing this user base.

### Top 3 Themes
- App crashes and technical instability during peak trading hours
- Order execution failures and stop-loss reliability issues
- Charting limitations and missing Flash Trading features

### Action Ideas
1. Resolve the 9:15 AM 'market not open' order execution error, audit end-to-end order reliability including stop-loss visibility in open positions, and invest in server resilience to eliminate crash-driven financial losses during peak trading hours.
2. Complete TradingView integration and add dual/split-chart view (index plus option simultaneously) in Flash Trading mode, and persist saved chart layouts including indicators, colors, and drawings across sessions to close the most repeated power-trader feature gap.
3. Audit and standardise brokerage pricing communication across all in-app onboarding, order, and confirmation screens to eliminate the advertised-versus-charged discrepancy, and introduce a dedicated Mutual Funds tab within INDStock to capture the high-frequency unmet demand flagged consistently across review periods.

---

