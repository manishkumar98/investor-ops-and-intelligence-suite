## Week of June 12, 2026

### Weekly Note
Synthesising reviews from late March through June 2026, three dominant pain points emerge that demand immediate product attention. Chart reliability and order execution are the most critical and trust-eroding issues: positions vanish from charts mid-session, TP/SL orders fail inconsistently on mobile, zoom gestures accidentally trigger order execution causing real monetary losses, and a kill switch is entirely absent. These are not cosmetic bugs — they are directly harming traders financially. Trading performance and lag compound the problem, with F&O and options sessions suffering slowness that undermines an otherwise well-regarded core experience. Users who praise the platform's brokerage and Flash features still flag lag as a growing concern, suggesting degradation over time rather than a baseline issue. Missing features and customisation gaps — limit sell orders for scalpers, dual-chart view, points-based SL/TP input, commodity trading, and broken watchlist functionality from the option chain — signal that the platform is not yet feature-complete for active traders. Secondary themes include UI complexity relative to simpler competitors and brokerage pricing discrepancies where promised Flash Trading rates are not automatically applied, creating distrust. On the positive side, Flash Scalping's one-click switching and influencer-driven acquisition show genuine product strengths worth protecting. Performance stability, charting reliability, and feature completeness are the top priorities this week.

### Top 3 Themes — Quotes — Actions

**1. Chart & Order Execution Bugs**
> "Sometimes the position vanished from the chart, TP/SL didn't work on mobile, from desktop browsers I can but that also depends on luck, if I use setup then it works sometime, and then position disappear from chart. So frustrating, and last day while zooming in/out the chart my position got executed in loss, just ridiculous."
→ Audit and fix the mobile charting engine immediately to eliminate position disappearance and accidental order execution on zoom gestures; enforce full TP/SL reliability on mobile at parity with desktop; add a prominently visible kill switch as an urgent trader safety feature.

**2. Trading Performance & Lag**
> "The best application with the best brokerage in the market really mast hai but recently while trading options it is getting little bit lag and slow can you check please"
→ Investigate and resolve F&O and options trading lag at both server and client levels; prioritise chart rendering performance under low-bandwidth conditions and monitor session stability continuously to prevent further degradation of the core trading experience.

**3. Missing Trading Features & Customisation**
> "customized watch list is not visible under watchlist. user preferences is allowed to add to watchlist from option chain which is missing. specific chart trend should be highlighted even at chart as well."
→ Ship limit sell orders and restore option-chain-to-watchlist add functionality; implement points-based SL/TP input alongside the existing percentage-based option; publish a public feature roadmap so active traders know when commodity trading, dual-chart view, and other requested features are planned.

---

## Week of June 5, 2026

### Weekly Note
Across both review batches this week, three themes dominate user feedback for INDMoney. Chart Bugs and UI Improvements is the most critical and recurring concern: users report positions vanishing from charts mid-session, TP/SL orders failing silently on mobile while working inconsistently on desktop, accidental trade executions triggered by zoom gestures causing real financial losses, and buy/sell buttons obstructing the full-screen chart experience. Requests for a points-based SL/TP input alongside the existing percentage mode were also raised. Performance and Lag is the second major theme, with options and F&O traders specifically reporting slowness during active trading sessions, as well as slow chart tile loading on weaker connections — issues that directly undermine time-sensitive trading decisions. Missing Trading Features rank third: users want dual-chart view, limit order sell functionality for scalpers, commodity trading support, and a kill switch for risk management — gaps that position INDMoney behind competitors on feature completeness. Brokerage fee transparency is a notable secondary concern, with at least one user charged standard rates despite being promised a discounted Flash Trading rate, eroding trust. Watchlist bugs — including customised lists not displaying and the add-to-watchlist shortcut missing from the option chain — also drew repeated complaints. Positive sentiment exists around low brokerage pricing when correctly applied, fast order execution, and the innovative Flash Scalping UI, which should be protected as key differentiators.

### Top 3 Themes — Quotes — Actions

**1. Chart Bugs & UI Improvements**
> "Sometimes the position vanished from the chart, TP/SL didn't work on mobile, from desktop browsers I can but that also depends on luck, if I use setup then it works sometime, and then position disappear from chart. So frustrating, and last day while zooming in/out the chart my position got executed in loss, just ridiculous."
→ Run a dedicated QA sprint targeting chart stability: fix position disappearance, TP/SL mobile failures, and zoom-triggered accidental executions; add a gesture-lock toggle to prevent unintended order placements during chart navigation; and relocate buy/sell buttons to a collapsible overlay to restore full-screen chart real estate, while also adding a points-based SL/TP input option.

**2. Performance & Lag Issues**
> "recently while trading options it is getting little bit lag and slow can you check please"
→ Conduct a thorough performance audit of the F&O and options trading flow to identify and resolve latency bottlenecks during active sessions, and implement progressive chart tile loading so charts render acceptably on slow or 3G connections.

**3. Missing Trading Features**
> "best app ...but dual chart view must needed"
→ Accelerate the roadmap for dual-chart view and limit order sell functionality; add a kill switch to the trading interface as a critical risk-management control; open a public feature-request tracker for trader upvoting; and evaluate a commodity trading beta to close the competitive feature gap.

---

## Week of May 29, 2026

### Weekly Note
Reviews spanning late April to late May 2026 reveal a broadly positive but friction-heavy experience for active F&O and Flash traders on INDMoney. Three themes dominate across both review sets. First, chart and UI issues are the most pervasive complaint: buy/sell buttons obstruct the full-screen chart, custom watchlists are absent or inaccessible from the option chain, and chart positions intermittently disappear — in one critical case causing an unintended loss during a zoom gesture, directly eroding trader trust and capital safety. Second, brokerage pricing and transparency is highly contentious: while one user unlocked a ₹10 Flash Trading brokerage and saved over ₹2500 monthly after contacting support, another reported being charged ₹20 despite a clearly communicated ₹10 promotional rate — signalling a systemic gap between advertised offers and actual billing. Third, TP/SL reliability remains a significant concern: Auto SL/TP executes inconsistently on mobile and unpredictably on desktop, and users are requesting a points-based absolute-value input to match competitor platforms. Secondary themes include app performance lag on charts and missing trading features such as a kill switch, limit-order sell for scalpers, and commodity trading. Positive signals include praise for the Flash Scalping interface's single-click call/put switching and low MTF interest rates. Immediate priorities should be fixing chart UI regressions and automating promotional brokerage activation to protect both trader capital and platform trust.

### Top 3 Themes — Quotes — Actions

**1. Chart & UI issues**
> "Sometimes the position vanished from the chart, TP/SL didn't work on mobile, from desktop browsers I can but that also depends on luck, if I use setup then it works sometime, and then position disappear from chart. So frustrating, and last day while zooming in/out the chart my position got executed in loss, just ridiculous."
→ Fix the full-screen chart experience by repositioning buy/sell buttons as a collapsible overlay, resolve the bug causing positions to vanish from charts mid-session, and enable watchlist customisation directly from the option chain to eliminate high-impact UI regressions affecting live traders.

**2. Brokerage pricing and transparency**
> "Flash trading se ind mony f&o me 1 year tak 10 rup.. Brokerage btaya tha Phir bhi 20 rupee Brokerage lag raha hai"
→ Automate reduced brokerage offer activation for all eligible Flash Trading users so the correct rate applies without requiring a support call, and add a real-time itemised brokerage breakdown on the order confirmation screen to fully eliminate billing confusion and honour communicated promotions.

**3. TP/SL functionality problems**
> "The experience is very smooth, and the Auto SL/TP feature is also very good. Please add a points-based SL/TP option along with the percentage option in Auto SL/TP. Also, the buy and sell buttons at the bottom significantly reduce the chart viewing area, which affects the full-screen chart experience."
→ Prioritise a hotfix for mobile Auto SL/TP execution reliability to prevent unintended losses, and add a points-based absolute-value input option alongside the existing percentage option in the Auto SL/TP feature to close the gap with competing platforms.

---

## Week of May 22, 2026

### Weekly Note
Reviews from late April to mid-May 2026 converge on three dominant pain points. Charting and UI is the single most recurring frustration: buy/sell buttons obstruct the chart canvas in full-screen mode, positions disappear visually mid-session, tablet layouts break when the floating window is active, and users strongly request a dual or triple chart view to monitor index and options simultaneously. These are not isolated complaints — they span multiple ratings and dates, signalling a structural product gap. TP/SL and order execution reliability is the most trust-critical issue: Auto SL/TP fails intermittently on mobile, a pinch-to-zoom gesture accidentally triggered a real loss, and a recurring 9:15 AM bug incorrectly blocks order placement despite the market being live for over a month — none of these have been resolved, eroding user confidence sharply. Brokerage pricing transparency is the third prominent theme: users report being charged ₹20 per order despite promotional promises of ₹10 under Flash Trading plans, with no in-app visibility into active plan status. On the positive side, flash scalping UI, fast execution on stable connections, affordable MTF rates, and responsive customer support remain strong differentiators. Overall sentiment skews negative in the 1–3 star band, with execution safety and billing trust as the most urgent areas requiring immediate product and engineering attention.

### Top 3 Themes — Quotes — Actions

**1. Charting & UI Issues**
> "The buy and sell buttons at the bottom significantly reduce the chart viewing area, which affects the full-screen chart experience. Kindly move these buttons elsewhere so the chart can remain fully visible in full-screen mode."
→ Redesign the full-screen chart layout by relocating buy/sell buttons to a collapsible overlay or swipe-up panel, eliminating canvas obstruction; simultaneously prioritise and ship a dual-chart (index + options) view and fix the floating-window font-scaling bug on tablets.

**2. TP/SL and Order Execution Bugs**
> "Sometimes the position vanished from the chart, TP/SL didn't work on mobile, from desktop browsers I can but that also depends on luck... last day while zooming in/out the chart my position got executed in loss, just ridiculous."
→ Treat mobile TP/SL execution failure and the 9:15 AM false market-open block as P1 bugs: audit the position-rendering and market-status check pipelines, add safeguards to prevent accidental order triggers during pinch-to-zoom gestures, and deploy fixes with full regression coverage.

**3. Brokerage Pricing & Transparency**
> "Flash trading se ind mony f&o me 1 year tak 10 rup.. Brokerage btaya tha Phir bhi 20 rupee Brokerage lag raha hai"
→ Surface all active brokerage promotional plans (e.g. Flash Trading ₹10/order) directly inside the app on a dedicated brokerage/plan settings screen with real-time status, so users never rely on support to discover or verify their plan, eliminating billing confusion and trust erosion.

---

## Week of May 15, 2026

### Weekly Note
Across both review batches, three themes emerge as the most urgent and recurring. Charting and position tracking reliability is the top concern: users report positions disappearing mid-session, TP/SL orders failing silently on mobile, and accidental trade executions triggered by zoom gestures — all carrying direct financial risk. This is the single highest-priority engineering issue on the platform. Missing or broken trading features rank second: the absence of a kill switch, no limit order sell option blocking scalpers, watchlist customisations not persisting, and inconsistent feature parity between mobile and desktop all point to incomplete core trading workflows. Brokerage pricing discrepancies are the third dominant theme: users report being promised reduced F&O rates via Flash Trading but consistently being charged the standard rate, eroding trust among active traders and generating avoidable support escalations. Beyond the top three, dual/multi-chart view is the single most-requested new feature, explicitly called a must-have by multiple users for side-by-side index and options analysis. App performance on slow networks, order execution glitches at market open (a persistent month-long 9:15 AM bug), commodity trading access requests, and promotion fulfilment gaps round out the broader feedback landscape. Overall sentiment is mixed-to-positive — users are enthusiastic about the platform's potential but trading reliability and pricing transparency must be addressed before growth features.

### Top 3 Themes — Quotes — Actions

**1. Charting and position tracking issues**
> "Sometimes the position vanished from the chart, TP/SL didn't work on mobile, from desktop browsers I can but that also depends on luck, if I use setup then it works sometime, and then position disappear from chart. So frustrating, and last day while zooming in/out the chart my position got executed in loss, just ridiculous."
→ Conduct an urgent engineering audit of the charting engine to fix position persistence bugs, ensure TP/SL orders execute reliably on mobile, add gesture-lock or a confirmation prompt during chart zoom to prevent accidental order triggers, and fix the persistent 9:15 AM market-open order execution error by tying market-status checks to a live exchange feed rather than a static timer.

**2. Missing or broken trading features**
> "customized watch list is not visible under watchlist. user preferences is allowed to add to watchlist from option chain which is missing. specific chart trend should be highlighted even at chart as well."
→ Prioritise shipping a kill switch, limit order sell functionality, and persistent watchlist and option chain preferences to close critical gaps in core trading workflows — then audit and enforce feature parity between mobile and desktop browser experiences across all trading surfaces.

**3. Brokerage charges and pricing discrepancies**
> "Flash trading se ind mony f&o me 1 year tak 10 rup.. Brokerage btaya tha Phir bhi 20 rupee Brokerage lag raha hai"
→ Audit the Flash Trading brokerage activation flow end-to-end to ensure promised rates are automatically applied at account level without manual support intervention, surface the active brokerage rate prominently on the order placement screen, and trigger proactive in-app confirmation when a promotional rate is successfully activated.

---

## Week of May 6, 2026

### Weekly Note
This week's INDMoney reviews across both batches point to three dominant pain points undermining user trust and retention. Trading bugs and technical glitches are the most urgent and wide-ranging concern: users report positions vanishing from charts, TP/SL orders failing on mobile, zoom-gesture-triggered accidental order executions, watchlists disappearing after updates, and a persistent month-long 9:15 AM market-open order rejection bug. Several of these issues directly cause financial losses, making them critical P0 priorities. Brokerage charges transparency is the second most prominent theme: multiple users explicitly report being charged ₹20 per order despite promotional Flash Trading plan promises of ₹10 or lower rates, with at least one user uninstalling the app over the discrepancy. This broken-promise dynamic is particularly damaging to trust. Missing or incomplete trading features round out the top three, with active and advanced traders requesting limit order sell functionality, a kill switch button, dual or triple chart view, commodity trading support, and automated chart pattern detection. On the positive side, users praised the flash scalping UI, fast order execution when working correctly, affordable MTF interest rates, and responsive customer support — signals that the core product proposition resonates strongly when it functions as intended. Overall sentiment skews negative due to reliability and pricing integrity issues, but loyalty potential is high among users who experience the product at its best.

### Top 3 Themes — Quotes — Actions

**1. Trading bugs and technical glitches**
> "Every day at 9:15 AM when I place an order, it shows 'Execute the order after market open' even though the market is already open and LTP is changing. This major glitch has been happening for over a month."
→ Immediately escalate all confirmed trading bugs — including the 9:15 AM order rejection glitch, chart position disappearance, TP/SL mobile failures, and zoom-triggered executions — as P0 incidents; deploy hotfixes within 48–72 hours and communicate resolution status in-app to affected users.

**2. Brokerage charges transparency**
> "Flash trading se ind mony f&o me 1 year tak 10 rup.. Brokerage btaya tha Phir bhi 20 rupee Brokerage lag raha hai"
→ Audit the Flash Trading plan brokerage application logic end-to-end to ensure promotional rates are correctly applied at the order level for all eligible users; add a pre-trade brokerage estimate tooltip in the order ticket and send a proactive in-app clarification to users who may have been overcharged.

**3. Missing or incomplete trading features**
> "there is no LIMIT order sell...not for scalper..."
→ Publish a transparent in-app feature roadmap covering limit order sell, kill switch, dual or triple chart view, commodity trading, and automated chart pattern detection — and introduce a demand-voting mechanism so active traders can prioritise features and feel acknowledged.

---

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

