# Vehicle Import File list and Excel

The eleven columns, in logical order (right to left in Arabic), are Name, Supplier,
Received Vehicles, Sold Vehicles, Remaining Vehicles, Purchase Value, Paid Amount,
Outstanding Amount, Status, Country of Origin and Supplier Currency.
`import_title`, `company`, `contract_number` and
`contract_date` are hidden from this list only. Their DocType fields, detail forms
and existing data are unchanged. Existing search and `modified desc` ordering are
preserved; totals and Previous/Next pagination are permission-aware.

## Calculation and currency policy

- Received Vehicles counts distinct nonempty VINs from readable Vehicle Master
  records linked by `vehicle_import_file` whose actual Purchase Receipt is
  submitted, not a return, and belongs to the same company. Draft/cancelled receipts
  and cancelled Vehicle Masters are excluded. Status text, disabled flags, expected
  quantities and cached receipt counters do not substitute for receipt evidence.
- Sold Vehicles is the subset of those VINs on readable submitted non-return Sales
  Invoice items through `custom_vehicle_master`. Drafts, cancelled invoices,
  reservations and delivery-only documents are not completed invoice sales.
  Submitted credit notes and stock-return Delivery Notes exclude only the actual
  returned VIN, using original invoice-item / delivery-item / parent-and-VIN links.
  A return of one vehicle does not remove the other vehicles on the same invoice;
  cancellation of a return restores the sale; a later valid resale counts again.
  A credit note and its stock return do not subtract the VIN twice.
- Remaining Vehicles is exactly Received minus Sold. Sets of VINs prevent item
  joins or repeated links from multiplying any count. Missing source permissions
  display `—` with a translated reason rather than treating unseen sales as zero.
  The original `vehicle_count` API value remains available for backward
  compatibility but is no longer a displayed/exported column. No receipt or sales
  status recalculation helper is called, because those operational helpers write.
- Purchase Value sums each readable non-cancelled Purchase Order parent once.
  Draft and submitted orders are included, matching the existing import workspace.
  The explicit `custom_vehicle_import_file` link is authoritative. For older orders
  with no explicit link, actual Vehicle Master `purchase_order` links are reused.
- All financial totals use **company currency**, shown in every amount cell.
  Purchase values use stored `base_grand_total`; allocations use the standard
  Payment Ledger Entry's company-currency `amount`. Today's exchange rates and the
  import file's supplier-currency label are never used to add mixed currencies.
- Submitted Purchase Invoices are located through their explicit import link or
  actual item `purchase_order` / `purchase_receipt` references. Return invoices
  also follow `return_against`. Cancelled invoices and delinked ledger entries are
  excluded. Invoice company, supplier and payable account must match the ledger.
- Paid Amount is the net active Payment Ledger allocation sourced by submitted,
  readable Payment Entries, plus allocated cash/bank Journal Entries. Unallocated
  advances are excluded. Native advance allocation and Payment Reconciliation are
  reflected by reading the current active ledger, rather than stale header amounts.
  A shared payment contributes only its allocation against each relevant invoice.
- Outstanding Amount starts with Purchase Value, subtracts normal invoice base
  totals and adds the current ledger outstanding of those invoices and their
  returns. Thus it retains the uninvoiced PO commitment and includes actual credit
  notes, write-offs, FX and rounding adjustments. In the ordinary case it equals
  Purchase Value minus allocated payments. Non-cash journal adjustments affect
  outstanding, not Paid Amount. This is a PO commitment measure, **not** a replacement
  for ERPNext's supplier Accounts Payable report. Credits may produce negative values.

No pro-rata allocation is invented for a legacy shared PO/invoice. Ambiguous
associations, missing company currency, unreadable accounting sources or incomplete
invoice ledgers show `—` with a translated reason. Legacy sharing is checked across
pages, so changing pagination cannot count a shared order twice. Readable empty
sets show zero. Financial columns are intentionally unavailable to users lacking
relevant source read permissions.

Queries are batched by the current page's import files, POs, receipts, invoices,
payments and journal entries. There are no per-file/per-vehicle source queries.
Additional bounded queries resolve legacy associations and journal cash accounts.
All reads use permission-aware Frappe APIs, including installed company/supplier
query-condition hooks and field permissions; no global permissions are changed.

## Excel behavior

Import Excel uses the existing modal styles and the company's currently selected
portal context. Download Template supplies editable import-file master fields:
Name (`import_title`), Supplier, Country of Origin, Supplier Currency, Expected
Vehicles, Exchange Rate and Notes. Company comes from the selection. The
received/sold/remaining counts, financial amounts and status are not writable through
Excel. The import template stays limited to editable master data; derived counts
come from real ERPNext documents after import.

Validation gives row numbers, names, statuses and native validation messages before
creation. The user can skip duplicates (default) or reject them. Existing names
are never updated. All rows are validated again on Import. If any row is invalid,
nothing is inserted; a late native save error rolls back the entire batch too.
Creation uses the actual Vehicle Import File controller and ordinary `insert()`,
including permissions, links, currency and quantity rules. Supplier read access,
enabled status and Company access are checked. No stock or financial documents are
created by this feature.

XLSX only: maximum 1,000 data rows, 2 MB upload and 20 MB expanded archive. Names and
supplier codes must be text to preserve leading zeros. Formula cells are rejected.
Templates format identifiers as text; the standard Frappe writer exports
formula-like strings literally. Workbooks are processed in memory without saving
uploaded files. Arabic and English template headers are accepted.

Export Excel requires native DocType export permission. It exports **all filtered
rows**, not just the visible page, in the same existing sort order and exact eleven
displayed columns. Computed values reuse the list's calculation/permission path.
Money cells include the currency code; unavailable values remain `—`. Headers and
statuses follow the selected language, Unicode is preserved, and Arabic worksheets
use RTL. Exports exceeding 20,000 rows require narrower filters rather than silently
truncating results.

## Changed files

- `an_truck_portal/api/records.py`: list enrichment and accurate pagination.
- `an_truck_portal/import_file_metrics.py`: batched permission-aware totals.
- `an_truck_portal/api/import_file_excel.py`: template, validation/import and export.
- `an_truck_portal/api/context.py`: expose the existing native export capability.
- `frontend/src/views/Records.vue`: eleven columns, amount formatting and Excel actions.
- `frontend/src/components/ImportFileExcelDialog.vue`: template/upload/row feedback.
- `frontend/src/api.js`: authenticated file downloads with existing error handling.
- `frontend/src/locales/{ar,en}.json`, `an_truck_portal/translations/ar.csv`.
- `an_truck_portal/tests/test_import_file_list.py` and
  `frontend/tests/import-file-list.browser.cjs`.
- This document and generated `an_truck_portal/public/frontend/manifest.json`,
  `an-truck-portal-DOYlUhpw.js`, `an-truck-portal-CLauoIMj.css` (replace old hashes).

## Focused verification on dev.localhost

```sh
bench --site dev.localhost run-tests --module an_truck_portal.tests.test_import_file_list
cd apps/an_truck_portal/frontend
npm run build
```

Seventeen integration tests pass. They cover receipt-backed VIN sets, completed
sales, partial-invoice returns, delivery returns, later resales, restricted source
permissions, deduplication, more than 20
orders, currencies, actual submitted invoice/payment allocations, shared payments,
returns/cancellations, advances, late native reconciliation, cash journals versus
non-cash adjustments, legacy item links/shared references across pages, permissions,
pagination, batching, workbook labels/Unicode/filtering, duplicates, invalid rows
and atomic rollback after a late save failure. Accounting/stock fixtures are
transactional and rolled back. Before/after fingerprints verify existing import
files, vehicles, orders, invoices, payments and accounting/stock ledgers are unchanged.

```sh
PORTAL_PLAYWRIGHT_PATH=/tmp/an-truck-browser-check/node_modules/playwright \
  node apps/an_truck_portal/frontend/tests/import-file-list.browser.cjs
```

The live browser check verifies Arabic RTL, English LTR, all eleven headers, real
counts/currencies, search, pagination, empty results, mobile layout, actual Excel
downloads, row validation and successful creation. It creates/deletes only uniquely
marked new import-file master fixtures and logs out its own session. It creates no
financial/stock transactions. Screenshots: `/tmp/import-file-list-{ar,en}*.png`
and `/tmp/import-file-excel-{ar,en}*.png`. No JavaScript page errors were observed.
Frontend production build, Python compilation and `git diff --check` also pass.

No schema change, migration, dependency installation, permission change or service
restart is required. Frontend assets are rebuilt. Deploy source and generated assets
together. No historical/financial records were changed, and no commit or push was
performed.
