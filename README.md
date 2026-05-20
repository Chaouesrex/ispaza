# spazi shops — AI Advisor for South African Spaza Shop Owners

> **Better decisions today.**

A Streamlit app built for the **IEB TechWays AI Hackathon 2026** under the
*Cross-Border Trade & Informal Economy* category.

spazi shops is an end-to-end operating tool for South African spaza shop
owners. The owner enters their current stock and last week's sales and
the app delivers four things at once:

1. **What to do about it** — restock / reprice / new-product advice in
   two formats: a worded brief or a one-line-per-action quick table
   (⬆️ Increase · ⬇️ Decrease · ⏸️ Hold, with the specific amount and
   a one-line reason).
2. **A purchase plan with real prices** — what to buy, from which
   supplier, on which day, at what unit cost, and what each combined
   trip costs (stock outlay + transport).
3. **Daily profit tracking** — per-product cost and selling price,
   revenue / cost / profit / margin per day, cumulative profit chart,
   and CSV export of every purchase and sale.
4. **A browsable product catalogue** — 17 products across 6 categories
   with cost, median price, margin, supplier and best day to buy.
   Search by name or supplier, filter by category, add-to-stock in
   one click.

**No API keys. No external services. No internet required.** The
recommender, the planner, the tracker, the catalogue, and the support
ticket system all run on-device.

The whole UI translates between **all 11 official South African
languages** — Afrikaans, English, isiNdebele, isiXhosa, isiZulu,
Sesotho, Sesotho sa Leboa, Setswana, siSwati, Tshivenḓa, Xitsonga —
via a language picker at the top of the sidebar.

---

## Run it locally

```powershell
# 1. Create a virtual environment (recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install runtime deps
pip install -r requirements.txt

# 3. Run
streamlit run app.py
```

Open the URL Streamlit prints (default: http://localhost:8501).

---

## Deploy it for free on Streamlit Community Cloud

1. Push this folder to a public GitHub repo.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in
   with GitHub.
3. Click **New app** → pick the repo, branch `main`, main file `app.py`.
4. Click **Deploy**. After ~2 minutes you get a permanent URL like
   `https://ispaza-<hash>.streamlit.app`.

The repo already contains everything Streamlit Cloud needs:

| File | Purpose |
|---|---|
| `requirements.txt` | Runtime Python deps |
| `.python-version` | Pins Python 3.11 on the cloud build |
| `.streamlit/config.toml` | Theme + headless server settings |
| `app.py` | Entry point |

### Other free hosts (alternatives)

- **Hugging Face Spaces** — create a Streamlit Space, push these files.
- **Render** — Web Service from the repo, build `pip install -r requirements.txt`,
  start `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`.

> **Vercel is not supported.** Streamlit needs a long-running server
> with WebSocket support; Vercel's serverless model can't host it.

---

## The four tabs

### 💡 Get Advice
Two editable tables — current stock and last week's sales — pre-filled
with realistic spaza items. One primary button. Two output modes you
toggle live:

- **Worded advice** — three card-style sections (Restock / Pricing /
  One to add) plus a confidence rating.
- **Quick actions** — a sortable table: one row per signal with the
  direction (⬆️ Increase / ⬇️ Decrease / ⏸️ Hold), what to adjust
  (Stock / Price), the specific amount, and a one-line reason. CSV
  download in one click.

### 💰 Profit Tracker
Four headline KPIs at the top: Revenue, Cost of goods, Profit, Margin.
Below that:

- **Daily profit chart** — green line for daily profit, yellow line
  for cumulative.
- **Per-product breakdown** — every product ranked by profit, with
  revenue, cost, profit and margin.
- **Units sold — by product** (bar chart) and **by day** (stacked bar
  chart). Shows which lines move fastest and how each day's mix breaks
  down across the catalogue.
- **Editable sales log** — one row per product per day. Unit price and
  unit cost are editable; revenue, cost, and profit recalculate live.
- **Editable purchase log** — every stock-in event with date, quantity,
  unit cost, total cost and supplier.

Both logs export to CSV.

### 🚚 Delivery & Purchasing
- **This week's purchase plan** — editable table: what to buy, unit
  cost, line cost, supplier, and a **Schedule** column with three
  modes: **Auto** (snap to the supplier's best day), **Manual** (pick
  your own date — useful when you're already going on a different
  day), or **Skip** (drop the line). The grand total under the table
  always reflects the current schedule selection: stock outlay **plus
  transport**, with skipped lines excluded.
- **Combined trips** — same plan re-grouped by (scheduled date,
  supplier), with separate **stock**, **transport** and **total**
  columns. R0 transport for direct delivery, ~R80 for Jumbo Cash &
  Carry pickups. If the same supplier is hit on two different
  scheduled dates (e.g. one Auto, one Manual), two trips appear.
- **Next 7 days** — concrete calendar for the upcoming week.
- **Typical week** — Mon→Sun reference grid.
- **Supplier notes** — channel, delivery days, lead time, transport
  cost, minimum order, and the gotcha for each supplier.

### 🆘 Help & Reports
A built-in support ticket system. Three things live here:

- **Create a new ticket** — subject, category (Advice quality, Pricing
  data, Delivery info, App bug, Other), priority (Low / Medium / High),
  free-form description. Submits to the in-session ticket store.
- **Your tickets** — every ticket rendered as a card with status,
  priority and category badges. Each card has an **Update status**
  button that cycles `Open → In progress → Resolved → Open`.
- **Show status** filter at the top right narrows the list to a
  single status.

Plus a one-click **Report a problem with this advice** button on the
Get Advice tab — opens a pre-filled ticket form that snapshots the
current advice mode and confidence so you don't have to retype the
context. Tickets are session-scoped (Streamlit Cloud has an ephemeral
filesystem); CSV download is the production path until a real DB lands.

### 🛍️ Browse Products
- **Search box** — free-text matches product name, supplier or category.
- **Category filter** — multiselect across snacks, soft drinks,
  staples, household, tinned food, groceries.
- **Product cards** — name, median selling price, cost, margin %,
  category, price range, supplier, best day, pack size. Each card has
  a quantity selector and an **➕ Add to my stock** button that pushes
  the product onto the Get Advice tab.
- **Full catalogue table** — collapsible, with the same data sortable
  by any column.

---

## How the advisor works

The recommender is **deterministic and runs locally** using real analysis
on the owner's data — sell-through rates, weeks of stock cover, benchmark
price medians, complement detection, and supplier patterns.

For every product the owner names, the advisor computes:

| Signal | Used for |
|---|---|
| **Sell-through** (sold ÷ (sold + remaining)) | Spotting hot movers and slow stock |
| **Weeks of cover** (remaining ÷ sold) | Ranking restock urgency |
| **Benchmark median** (from `data/benchmarks.json`) | Pricing nudges |
| **Wholesale pack size** | Rounding orders to a real-world unit (case of 24, etc.) |
| **Cost price** | Profit and margin computations |
| **Supplier + delivery day + transport cost** | Routing each restock to the right trip |
| **Complement votes** (from top sellers' complements) | The "one to add" pick |

Worded mode emits markdown matching the three-section contract; quick
mode emits a sorted DataFrame of one-line actions.

---

## What's in the box

```
ispaza/
├── app.py                  # Streamlit UI (single entry point)
├── advisor.py              # Worded recommender (three-section markdown)
├── quick_actions.py        # ⬆️/⬇️/⏸️ recommender (DataFrame of bumps)
├── tracker.py              # Purchase log + daily profit + units charts
├── delivery.py             # Weekly schedule + opinionated purchase plan
├── catalog.py              # Product browse, filter, add-to-stock
├── support.py              # Support ticket CRUD + filter + CSV export
├── i18n.py                 # Translation lookup + locale registry
├── core.py                 # Shared helpers (loaders, parser, defaults)
├── data/
│   ├── benchmarks.json     # 17 products: prices, costs, suppliers, days
│   ├── suppliers.json      # 4 SA-township supplier patterns + transport
│   └── i18n.json           # UI strings × 11 official languages
├── tests/
│   ├── conftest.py
│   ├── test_core.py
│   ├── test_advisor.py
│   ├── test_quick_actions.py
│   ├── test_tracker.py
│   ├── test_delivery.py
│   ├── test_catalog.py
│   ├── test_support.py
│   └── test_i18n.py
├── .streamlit/config.toml  # Brand colours (SA green + accent yellow)
├── .python-version         # Pins Python 3.11 for hosted deploys
├── requirements.txt        # Runtime deps (streamlit, pandas, numpy)
├── requirements-dev.txt    # Runtime deps + pytest
└── README.md
```

## A note on the translations

`data/i18n.json` ships full UI translations for **English, Afrikaans,
isiZulu, isiXhosa**. The other seven official languages (isiNdebele,
siSwati, Sesotho, Sesotho sa Leboa, Setswana, Tshivenḓa, Xitsonga)
have the critical UI surface translated — tabs, buttons, headers,
status labels, the ticket form — with a tested completeness floor
defined by `CRITICAL_KEYS` in `i18n.py`. Long body paragraphs (banners,
help text) fall back to English in those locales until a native-speaker
review pass lands.

Translations are AI-assisted starting points. PRs from native speakers
are very welcome — open one against `data/i18n.json` and the test suite
will tell you if you missed a critical key.

All business logic lives in pure Python modules so the entire app can
be unit-tested without launching Streamlit.

---

## The supplier patterns

`data/suppliers.json` encodes four realistic SA-township routes:

| Supplier | Channel | Delivery days | Best to order | Transport | Min order |
|---|---|---|---|---|---|
| **Sasko bakery route** | Direct delivery | Mon–Sat | Daily | free | none |
| **Coca-Cola SA depot** | Direct delivery | Tue, Thu | Monday | free | R500 |
| **Simba (PepsiCo) rep** | Direct delivery | Wed | Tuesday | free | R300 |
| **Jumbo Cash & Carry** | Cash & carry | Tue, Wed | Tuesday | R80/trip | none |

Each product in `benchmarks.json` lists its supplier, delivery days,
best purchase day, cost price, and wholesale pack size. The purchase
plan in `delivery.py` joins those facts to the live signals from the
owner's stock and sales to produce the operational view, then
`trip_summary` adds the supplier's transport cost on top.

---

## Running the tests

```powershell
pip install -r requirements-dev.txt
pytest -v
```

Coverage by module:

- **`test_core.py`** — benchmarks loader, response parser, total-units
- **`test_advisor.py`** — restock ranking, pricing nudges, complement
  picks, confidence scaling, edge cases
- **`test_quick_actions.py`** — direction labels, Increase/Decrease/Hold
  recognition, hold catch-all, CSV header
- **`test_tracker.py`** — Purchase/Sale dataclasses, daily/per-product
  profit breakdown, running totals, deterministic seed data with
  weekend boost, margin computation with zero-revenue safety
- **`test_delivery.py`** — weekly grid shape, supplier-day mapping,
  filtering by stocked products, purchase plan urgency, pack-size
  rounding, trip grouping with transport cost
- **`test_catalog.py`** — catalogue shape, margin computation, filter
  by query/category/both, add-to-stock append-or-increment semantics

---

## Out of scope (intentionally)

No auth, no real database, no WhatsApp integration, no bank API
integration, no multilingual UI. The production roadmap (WhatsApp,
voice notes, isiZulu/Sesotho, alternative credit history for
micro-loans) is documented separately.
