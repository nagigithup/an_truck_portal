# Add Cost to One Truck — native serial revaluation

Verified on `dev.localhost`, 2026-11-09, Frappe 16.54.0 / ERPNext 16.53.0.
The user explicitly approved Stock Reconciliation for unsold, on-hand VINs after
reviewing its native -1/+1 valuation legs and zero net quantity change.

## Document choice and scope

The existing popup, inputs and bulk landed-cost workflow are retained.

- An original one-unit receipt item containing exactly the selected VIN continues
  using a standard **Landed Cost Voucher / Distribute Manually**. Its native
  account currency, exchange rate and allocation behavior are unchanged.
- A multi-unit receipt item uses a separately identified standard **Stock
  Reconciliation**, selecting only the target VIN. It never presents receipt-row
  allocation as VIN allocation. Confirmation names the actual document type and
  shows current/new serial valuation, VIN, original receipt, import file,
  warehouse, account, amount and currency.
- Native LCV allocation remains prohibited for a marked single-truck voucher
  against a shared receipt row, including attempts through Desk or API.

[Native allocation audit and experimental results](single_truck_cost_serial_allocation_audit.md).

The selected-serial route requires native Serial No Wise Valuation, an active
submitted original receipt, matching Vehicle Master / receipt item / import file /
company, and the actual VIN still on hand in a readable company warehouse.
The current warehouse is obtained from native serial records, rather than assumed
from the historical receipt. Native serial availability and incoming-rate APIs
verify that VIN at posting time. Sold/delivered trucks, active invoice/delivery
serial history and unsupported or untracked valuation differences are blocked.
Returned sale history is conservatively blocked for finance review as well.
The existing one-unit LCV route retains its normal ERPNext reposting behavior.

## Native accounting and cost integration

Stock Reconciliation uses `purpose = Stock Reconciliation`, one native incoming
serial bundle, `reconcile_all_serial_batch = 0`, and `qty = current_qty = 1`.
The native controller generates the matching selected-serial outgoing bundle and
its own stock/GL entries. There is no Stock Entry, receipt splitting/amendment,
manual stock/GL edit or second accounting ledger. Net quantity stays unchanged.
The final native value difference must match the reviewed additional cost.

This route requires an enabled expense leaf account **in company currency**.
It uses the existing company expense-account options and native expense-account,
cost-center, dimension, period, freeze, serial and stock validation. It does not
invent an exchange rate or a foreign-currency Stock Reconciliation feature.
Foreign-currency expenses need finance's normal currency/accounting process;
original one-unit LCV currency support is preserved.

Vehicle Master retains its purchase and LCV breakdown. The additive read-only
`custom_portal_serial_cost_adjustment` and final valuation derive from the native
original receipt valuation plus submitted, explicitly linked Stock Reconciliation
`difference_amount` values. Submitted/cancelled tagged documents provide the
audit scope; no old vehicles are backfilled. Only the selected vehicle is refreshed
by its posting/cancellation/repost hook. Other vehicle identities and costs are
untouched, except normal existing bulk costs when deliberately posted.

Native reconciliation stores an absolute valuation, not a permanent incremental
charge. If a later bulk LCV changes the original receipt, ERPNext may recalculate
the reconciliation's posted difference. History and Vehicle Master use this actual
native difference, while the original requested amount remains available for audit.
For example, receipt 1,000 -> target 6,000 initially posts 5,000; a subsequent
100-per-truck bulk charge makes the posted reconciliation difference 4,900 and
keeps that VIN at 6,000. This native behavior is tested and is not overridden.

Cancellation uses native ERPNext validation and reversals. Multiple targeted
adjustments for one VIN must be cancelled newest first. It restores the derived
Vehicle Master value and removes cancelled amounts from active cost totals.
A later genuine sale uses the actual revalued serial cost in native COGS.

## Permissions, history, retries and atomicity

Portal access, readable mutable import file and Company, and native
read/create/submit permission for the selected document type are required.
Vehicle, Item, Serial No, receipt, warehouse and account reads respect existing
permissions and Company User Permissions. Nothing grants or bypasses user rights.
An internal stock-posting hook refreshes only the linked derived vehicle summary,
using the same trusted-summary pattern as the existing landed-cost hook.

The popup retains its confirmation fingerprint and stable retry key. Creation
locks the import file, vehicle, original receipt and selected Serial No; repeats
look up the request across both native document types. A unique persisted key
and normalized payload prevent retries from creating a second voucher. A new
request key permits another legitimate additional cost for the same VIN.
Stale stock/rate/source data requires renewed confirmation. Cancelled requests
are not silently recreated. Preview creates no document or serial bundle.
All native bundle creation, insert, submit and derived cost updates share a
savepoint and roll back together on failure, including failures after stock posting.

The current import-file cost history, totals, activity and linked-document view
include tagged Stock Reconciliations with their actual type, native amount and
VIN/notes. The portal has a read-only detail route `/serial-revaluations/:name`
showing the original receipt, requested amount, posted change and valuation.
Arabic/English and RTL/LTR use existing translation files. Mobile confirmation
scrolls internally and retains visible footer actions.

## Additive setup

Both apps must be deployed together. The version-controlled install/after-migrate
setup adds eight read-only audit fields on Stock Reconciliation: vehicle, import
file, original receipt, original receipt item, requested amount, description,
unique request hash and payload hash. It adds the read-only derived adjustment
field on Vehicle Master. Existing single-truck LCV fields are retained.
No accounts, warehouses, Items, balances or financial transactions are created.

Targeted commands, already applied locally:

```sh
bench --site dev.localhost execute an_truck_portal.setup.ensure_single_truck_cost_fields
bench --site dev.localhost execute an_truck_portal.setup.ensure_serial_revaluation_fields
```

Normal future app migration also calls these installers. No full migration or
bench restart was used for this change. Normal frontend assets are included.

## Modified source files

`an_truck`:

- `an_truck/serial_vehicle_cost.py`: native-document-derived valuation and hooks.
- `an_truck/an_truck/doctype/vehicle_master/vehicle_master.py`: derived cost read.
- `an_truck/transactions.py`: existing history, totals, permissions and documents.

`an_truck_portal`:

- `an_truck_portal/single_truck_cost.py`, `api/import_file.py`: native route,
  serial proof, scope, preview, creation, audit guards and read-only detail API.
- `an_truck_portal/setup.py`, `hooks.py`: additive fields and document events.
- `frontend/src/components/SingleTruckCostDialog.vue`, `VehicleDrawer.vue`:
  document/valuation confirmation and cost breakdown.
- `frontend/src/views/ImportWorkspace.vue`, `SerialRevaluationDetail.vue`,
  `frontend/src/router.js`: history integration, actual document navigation.
- `frontend/src/locales/{ar,en}.json`, `an_truck_portal/translations/ar.csv`.
- Focused backend/browser tests, these two documents, frontend manifest and
  its generated JS/CSS assets.

## Focused verification

```sh
bench --site dev.localhost run-tests --module an_truck_portal.tests.test_single_truck_cost
cd apps/an_truck_portal/frontend
npm run build
```

Seventeen rollback-only integration tests pass, including:

- Ten VINs in one original receipt item, 1,000 each, adding 5,000 to one: native
  rates are **6,000 / 1,000 x 9**, Bin quantity 10 / value 15,000, native balanced
  GL 5,000, and matching Vehicle Master cost. Original PR and other nine complete
  Vehicle Master documents remain identical.
- Native LCV experiment proving the same cost is shared 500 per VIN; forged
  row-level VIN allocation remains blocked; ordinary bulk workflow unchanged.
- History/detail, sequential duplicate retry, independent second cost,
  newest-first cancellation, audit links, stale confirmation and rollback after
  native submission failure, without orphan bundles or partial cost changes.
- Real subsequent sale posts COGS 6,000; sold-VIN revaluation is rejected.
- Later native bulk LCV/reposting preserves master/serial/GL consistency.
- Native foreign-currency one-unit LCV, company-currency-only serial adjustment,
  pooled-valuation denial, restricted users and normal Stock Manager submission
  of both document types within its allowed company.

```sh
PORTAL_PLAYWRIGHT_PATH=/tmp/an-truck-browser-check/node_modules/playwright \
  node apps/an_truck_portal/frontend/tests/single-truck-cost.browser.cjs
```

Live browser verification passes Arabic RTL, English LTR, mobile bounds/scrolling,
existing bulk popup, both native previews, foreign-VIN denial, stable retry key,
stale-confirmation recovery and no console page errors. Submit requests are
intercepted so no existing vehicle receives a cost. Business-record fingerprints
before/after browser and every backend test confirm existing data is unchanged.
The new read-only detail page is also checked in both languages and on mobile
with a fixture API response; its native document data is tested by the backend.
Screenshots: `/tmp/single-truck-cost-{ar,en}-shared-row{,-mobile}.png`.

True simultaneous committed posting and queued background-worker execution were
not run against this development site's existing stock; database locks, unique
request fields, sequential retry and native repost behavior were verified.
The installed unrelated Medatronics Company permission hook can restrict normal
Company reads. Tests preserve that denial and use a rolled-back native Company
read share for their own disposable stock user; no live grants were added.

No ERPNext core changes, historical data corrections, commits or pushes.
