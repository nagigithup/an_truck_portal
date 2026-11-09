# Add Cost to One Truck

The import workspace now offers **Add Cost to One Truck / إضافة تكلفة لشاحنة واحدة**
beside its existing bulk cost buttons. Existing bulk buttons, dialog, API, account
options and allocation behavior are unchanged.

## ERPNext v16 allocation audit

The installed `LandedCostVoucher.get_items_from_purchase_receipts()` loads whole
receipt items. `StockController.set_landed_cost_voucher_amount()` accumulates
submitted charges by `purchase_receipt_item`. Native receipt valuation then
revalues that item's stock quantity and serials. A Landed Cost Item has no native
selector for allocating to an individual VIN inside a multi-unit receipt row.
Changing the LCV quantity to 1 does not isolate one VIN in a quantity-2 receipt row.

Accordingly this feature supports only an original **one-unit stock receipt row
containing exactly the selected VIN**. It checks:

- The Vehicle Master belongs to the current import file and company, is enabled,
  and has actual Purchase Receipt / Purchase Receipt Item references.
- The receipt is submitted, not a return, and has the same company and explicit
  import-file link. The original row's item matches the vehicle's item.
- Receipt `qty` and `stock_qty` are both exactly 1, accepted/received quantity is
  one, rejected quantity is zero, and the serialized stock item is not a fixed asset.
- Native serial / Serial and Batch Bundle extraction yields exactly one serial,
  matching the VIN. Leading zeros and VIN spelling are never changed.

Multiple units, multiple VINs, UOM conversions producing multiple stock units,
rejected quantities, missing serial proof or inconsistent links are blocked. The
popup displays an explanation and disables Review Cost. Both the final API and
the targeted-voucher Desk validation enforce the same invariant. There is no
automatic splitting, amendment or restructuring of historical receipts. Future
one-truck costing requires an eligible original receipt row; bulk costing remains
available for multi-truck rows.

## Popup and native accounting

The popup reuses `FormField`, native dialog styling and existing company expense
account options. VIN search is server-side, permission-aware, limited to the current
import file and bounded to 30 suggestions. Typing a foreign VIN cannot bypass scope.
Selecting a truck loads its identity, source receipt, warehouse and currencies.

The entered amount is in the **selected expense account's currency**. The native
LCV controller supplies the account currency, exchange rate, company amount and
normal account/dimension validations. No SAR/USD rate is hardcoded. Description
is optional; the tax/charge row always includes the exact VIN for audit/history.

Review Cost is read-only. It builds an unsaved standard LCV and returns the actual
native calculation and a confirmation fingerprint. The review shows VIN, target
vehicle, import file, company, source warehouse, receipt, receipt currency, entered
amount/currency, company amount, exchange rate, expense account and description.
Final submission recalculates server-side and rejects changed confirmation data.

The resulting standard LCV has exactly one original receipt item and one cost row,
uses **Distribute Manually**, and assigns 100% of its native company-currency
`total_taxes_and_charges` to that item's `applicable_charges`. Normal `insert()` /
`submit()` apply Frappe permissions, workflows and ERPNext validation. It does not
post custom GL, update valuations manually or add a second inventory ledger.

Authorized submission necessarily invokes ERPNext's usual receipt valuation,
serial valuation, stock/GL reposting and future-reposting behavior. No existing
receipt is manually edited or split. Implementation/testing did not submit an LCV
against historical site data. There is no backfill or data correction migration.

The existing AN Truck cost-change hook now limits Vehicle Master refreshes to the
targeted vehicle **only when the new target field is populated**. Bulk vouchers
continue refreshing their existing full receipt scope. Other vehicles' master
records are not resaved by a single-truck cost. ERPNext may refresh valuation
metadata on a receipt's other serials during its native repost; their allocated
additional cost remains zero.

The existing `custom_vehicle_import_file` link makes the new voucher appear in
the current import-file documents and cost history, including its VIN description.
The new read-only vehicle link additionally provides direct audit navigation.

## Permissions, retries and atomicity

The API requires portal access, a readable mutable import file and Company, and
native LCV read/create/submit permissions. Vehicle, receipt, item, warehouse and
account document read permissions are also checked. Company User Permissions stay
in force. Completed/cancelled files and invalid source documents cannot be used.

Local normal-user verification also encountered an existing installed
`medatronics.security.ledger_company_permission` hook denying Company read to the
new stock test user. This feature preserves that denial. The positive normal-user
test used a native explicit Company read share for its new test user, then rolled
the share back. No live permission grants or Medatronics files were changed.
Deployment users must already have readable company/source/account records; this
feature does not correct unrelated global permission-hook configuration.

Every popup opening has a request key, preserved for retries/double clicks. The
server stores a durable unique hash bound to the import file, user and key, plus
the normalized payload hash. It locks the import-file row and performs locking
reads for an existing request. A matching submitted request returns its existing
LCV; different data with the same key is rejected. Cancelled requests are not silently
recreated. A new key permits a legitimate separate cost for the same VIN.

The unique database field provides an additional duplicate guard. There is no
one-hour cache expiry. Creating/submitting runs in the request transaction with a
savepoint: even a native failure after valuation changes rolls back the voucher
and those changes. The popup disables input during submission and offers the same
request on a network error. Closing/reopening intentionally starts a separate
request; verify the existing history before starting another cost after abandoning
an uncertain request.

True simultaneous committed posting was not run on this development site's live
stock. Sequential retries and native failure/retry paths were exercised; database
row locks and the unique request field implement the concurrency protection.

## Additive setup and deployment

`an_truck_portal.setup.ensure_single_truck_cost_fields` creates only these LCV
Custom Fields, leaving old voucher values empty:

| Field | Purpose |
| --- | --- |
| `custom_portal_truck_cost_vehicle` | Read-only Vehicle Master Link, hidden when empty, not copied |
| `custom_portal_truck_cost_request` | Hidden unique request hash, not copied |
| `custom_portal_truck_cost_payload` | Hidden normalized payload hash, not copied |

The version-controlled setup is called on install and after migrate. Deploy both
the small `an_truck` service-hook change and `an_truck_portal` changes together.
Local setup was applied without a full migration using:

```sh
bench --site dev.localhost execute an_truck_portal.setup.ensure_single_truck_cost_fields
```

Normal cloud migration also installs these fields. Alternatively run that targeted
command with the intended site after updating both apps. No account, warehouse,
Item, opening balance or financial transaction setup is created. The committed
frontend manifest/assets are rebuilt; deploy them with the source.

## Changed files

In `an_truck`:

- `an_truck/services.py`: limit targeted-voucher VM refresh to its actual vehicle;
  keep the bulk branch unchanged.

In `an_truck_portal`:

- `an_truck_portal/single_truck_cost.py`: eligibility, preview, native creation,
  durable deduplication and targeted-voucher validation.
- `an_truck_portal/api/import_file.py`: small permission-checked API adapters.
- `an_truck_portal/setup.py`, `an_truck_portal/hooks.py`: additive fields and guard.
- `frontend/src/components/SingleTruckCostDialog.vue` and
  `frontend/src/views/ImportWorkspace.vue`: independent popup and adjacent buttons.
- `frontend/src/locales/{ar,en}.json`, `an_truck_portal/translations/ar.csv`.
- `an_truck_portal/tests/test_single_truck_cost.py`,
  `frontend/tests/single-truck-cost.browser.cjs`, this document, and generated
  `an_truck_portal/public/frontend/manifest.json` plus the referenced JS/CSS assets.

## Focused verification

```sh
bench --site dev.localhost run-tests --module an_truck_portal.tests.test_single_truck_cost
cd apps/an_truck_portal/frontend
npm run build
```

Eight rollback-based integration tests exercise real new receipt/LCV submission
and cancellation, exact per-VIN allocation, unchanged other vehicle masters,
existing history links, shared-row and forged-quantity blocking, durable retry,
separate additional costs, native rollback after a post-valuation failure, account
currency conversion, confirmation changes, import/company scope, restricted users,
a normal Stock Manager submission, and unchanged bulk allocation. Before/after
fingerprints verify existing receipt/vehicle/stock/accounting documents are unchanged.

```sh
PORTAL_PLAYWRIGHT_PATH=/tmp/an-truck-browser-check/node_modules/playwright \
  node apps/an_truck_portal/frontend/tests/single-truck-cost.browser.cjs
```

The live browser check verifies Arabic/English, RTL/LTR, mobile scrolling and visible
footer, existing bulk dialog, live native previews, foreign VIN denial, the
translated multi-unit explanation, identical request keys on retry and renewed
review after stale confirmation. Create
requests are intercepted/aborted, so it posts **no** voucher against existing data.
It fingerprints business documents before/after and creates/logs out only its own
session. Screenshots: `/tmp/single-truck-cost-{ar,en}*.png`. Python compilation,
frontend build and both repositories' `git diff --check` pass.
