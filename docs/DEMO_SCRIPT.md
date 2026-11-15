# PortfolioGuard AI five-minute demo script

Storyline: the same request from two investors gets two different, evidence-backed
answers. The advisor pushes back when a request does not fit.

## Before recording

- Start the backend and frontend, and confirm `/health` and the dashboard service
  dots (FastAPI, S3, Lambda, Bedrock).
- Run each live call once to warm the Lambda.
- Use fictional personas only. Keep CloudWatch Logs open in a separate tab.

## 0:00–0:30: Problem

"Most investment tools agree with you. If Robert, 59 and close to retirement, reads
about NVIDIA, he gets a buy button. PortfolioGuard AI is an advisor that knows when
to say no, and shows its evidence."

Show the landing page and switch personas to show that each one has its own scenario.

## 0:30–1:30: Amira asks for NVDA

Open the dashboard with **Amira**. In **Suitability challenge**, click
"Put 25% of my TFSA in NVDA".

"The request parser extracts NVDA at 25%. The challenge agent builds three
allocations: as requested, a capped version, and a diversified growth alternative.
One Lambda call measures all of them on the same calendar and replays 2022."

Point at the verdict: **a smaller position fits**. NVDA would total 32.5% of her
portfolio, above her 15% single-company cap. "High risk does not mean anything goes."

## 1:30–2:45: Robert asks for the same thing

Switch to **Robert** and click "Put 25% of my RRSP in NVDA".

"Same request, different investor. In a 2022 replay that portfolio fell -22.4%,
about $101,000 of his fictional balance, against a -15% loss budget. The capped 5%
version fell -11.2% and fits."

Click the **-22.4%** chip. "Bedrock wrote the sentence but not the number. Code
inserted it from Lambda evidence. Here is its evidence ID, raw value, formula
version, and the versioned S3 object it came from."

Scroll to the scenario table and the trace: parser, challenge agent, Lambda,
governance, verdict, Bedrock.

## 2:45–3:30: Mateo's values

Switch to **Mateo** and click "Put 10% in Exxon".

"Mateo cares about ESG. Exxon is screened out by sector, using sector data from the
dataset rather than an opinion, so there is no capped version. The system recommends
the ESG basket. It is also honest that in 2022 the ESG basket fell more than the
Exxon request did. Values have a measured cost, and we show it."

## 3:30–4:20: Scenario analysis, stress, robustness

Click **Run live analysis** for Robert's scenario (15% from preservation into growth).

"Risk increases. The 2022 replay goes from -8.7% to -14.7%, close to his -15%
budget, and recovery goes from 8 to 15 months. The conclusion is marked *Robust*
because it holds on the full five-year history, which includes 2022."

## 4:20–4:45: AWS proof

Show CloudWatch `calculation_started` and `calculation_completed` with the same
analysis ID. Mention S3 manifest checksum verification and least-privilege IAM.

## 4:45–5:00: Close

"PortfolioGuard AI adapts to the investor, pushes back with evidence, and lets you
verify every number. Simulation only, not financial advice."

## Failure recovery

If AWS fails, keep the honest error state visible. Local placeholders are
intentionally disabled. Show a timestamped earlier real run, clearly labeled as such.