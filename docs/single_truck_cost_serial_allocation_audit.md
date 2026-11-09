# Serial-specific capitalization audit — 2026-11-09

Site: `dev.localhost`. Installed Frappe `16.54.0`, ERPNext `16.53.0`.
This is the initial pre-approval audit, preserved as evidence. The subsequently
approved native route is implemented and documented in [the current feature
guide](single_truck_cost.md). The descriptions below refer to the audit stage.

At that stage this audit changed tests/documentation only. The popup, bulk costing, single-truck
API, existing one-unit safety guard and accounting configuration are unchanged.
Nothing was committed or pushed. All experimental transactions were new fixtures
inside rolled-back test transactions; no existing receipt was split or amended.

## Findings and decision required

**Native LCV manual allocation is receipt-item allocation, not serial allocation.**
Removing the guard for a quantity-10 receipt would allocate the cost to all ten
VINs. The guard therefore remains in place.

**Native Stock Reconciliation can revalue a selected on-hand serial independently.**
That is a separate standard accounting/stock document, not an LCV. The experiment
used its supported selected-serial mode with `reconcile_all_serial_batch = 0`,
one selected serial bundle, `qty = current_qty = 1`, and a valuation increase of
SAR 5,000. ERPNext generated its own -1/+1 valuation legs, with no net quantity
change. No Stock Entry, transfer, repack, manual GL/SLE update, receipt amendment
or hand-edited valuation was used.

The user's restriction on artificial stock movements needs an explicit workflow
decision before routing the existing popup to this different document type. The
choice requested in this session is whether to retain the LCV limitation report
or implement a separately identified native Stock Reconciliation route for
eligible on-hand trucks. No custom accounting solution has been implemented.

## Native source evidence

The following installed ERPNext implementation was inspected, without modifying it:

- `stock/doctype/landed_cost_voucher/landed_cost_voucher.py`:
  `get_items_from_purchase_receipts()` loads receipt rows. Manual mode skips the
  automatic row distribution; `validate_applicable_charges_for_item()` checks
  total row charges. `update_landed_cost()` refreshes the original receipt's
  valuations and uses normal stock/GL reposting.
- `stock/doctype/landed_cost_item/landed_cost_item.json`: the allocation reference
  is `purchase_receipt_item`; there is no VIN/Serial No selector in this child.
- `controllers/stock_controller.py`, `set_landed_cost_voucher_amount()`: charge
  totals are accumulated by original receipt item, not serial number.
- `controllers/buying_controller.py`, `update_valuation_rate()`: receipt item
  valuation is `(base_net_amount + item_tax_amount + landed_cost_voucher_amount +
  applicable native adjustments) / stock quantity`.
- Native LCV `update_rate_in_serial_no_for_non_asset_items()` assigns the receipt
  row's resulting rate to the serials in that row. Serial/bundle processing also
  follows that row valuation. Manually changing only the LCV child quantity does
  not add a supported VIN allocation reference to the original row.
- `stock/doctype/stock_reconciliation/stock_reconciliation.py`:
  `get_bundle_for_specific_serial_batch()` selects only supplied serials that
  actually exist in the warehouse at the posting time.
  `get_sle_for_serialized_items()` posts native outward/current and inward/new
  valuation entries. The tested pair was -1 and +1, both for the same selected VIN.
- `stock/serial_batch_bundle.py`, `SerialNoValuation`, and native
  `stock/utils.py::get_incoming_rate()` resolve the individual serial's rate.
- `stock/doctype/stock_reconciliation/test_stock_reconciliation.py` contains
  `test_not_reconcile_all_serial_nos`, an existing native selected-serial example.

The installed `Adjustment Entry` purpose is not a generic additional-cost API.
`stock/valuation_adjustment.py::validate_made_from_report()` restricts it to the
Stock Valuation Comparison system workflow, whose expected-stock plan must match.
Its system flag must not be forged to book an arbitrary extra cost. Repost Item
Valuation recomputes from source documents; it is not an independent new cost.
Editing `Serial No.purchase_rate` alone is not a supported accounting solution.

## Reproducible SAR 5,000 / ten-truck results

Each scenario received ten unique VINs in **one Purchase Receipt Item**, at
SAR 1,000 each. The item used native Serial No Wise Valuation. Total opening
inventory from this new receipt was ten trucks / SAR 10,000, with no opening-stock
voucher or opening-balance change.

| Measurement | Before | Native manual LCV | Selected-serial Stock Reconciliation |
| --- | ---: | ---: | ---: |
| Target VIN's native incoming valuation | 1,000 | 1,500 | 6,000 |
| Each of the other nine VINs | 1,000 | 1,500 | 1,000 |
| Quantity in warehouse | 10 | 10 | 10 |
| Inventory value | 10,000 | 15,000 | 15,000 |
| Targeted new stock-ledger legs | — | Receipt row repost | -1 / +1 for selected VIN |
| Additional accounting value | — | 5,000 | 5,000 |
| Target Vehicle Master final value | 1,000 | 1,500 | **1,000: existing PR-based read** |

For LCV, the original receipt's active GL balanced at SAR 15,000 debit and credit,
including SAR 5,000 credited to the configured cost account. All ten vehicle
masters agreed with the shared native rate of SAR 1,500. This is correct **bulk**
costing, and incorrect for the requested one-VIN cost.

For the selected-serial reconciliation, native GL debits/credits were SAR 5,000
each, stock value rose by SAR 5,000, quantity remained ten, and native valuation
of the other nine VINs remained SAR 1,000. The original Purchase Receipt document
and the other nine Vehicle Master documents remained identical. The target
Vehicle Master still reported SAR 1,000 because its current implementation reads
the original receipt and row-level LCV amounts, not later serial revaluations.
That mismatch is explicitly asserted by the audit test, not concealed by a manual
Vehicle Master valuation update.

## Sold vehicle safety

A third scenario created a genuine standard update-stock Sales Invoice for one
of the ten new trucks, using its actual VIN. After sale:

- Remaining quantity was nine and inventory value SAR 9,000.
- The sold VIN was absent from the native available-serial query.
- Native posted COGS was SAR 1,000.
- Attempting the portal's SAR 5,000 single-truck LCV on the shared source row was
  rejected before any cost voucher was created; the nine remaining trucks,
  inventory and Vehicle Master costs remained unchanged.

An on-hand serial revaluation is not a sold-vehicle cost correction. Counting a
sold VIN back into stock just to increase its value would violate the requested
quantity constraint. No such reconciliation was made. Sold shared-row vehicles
must remain blocked until finance approves a supported post-sale cost treatment;
this audit does not invent that treatment or alter historical sales/COGS.

## Safe alternatives

1. For future **LCV-based** one-truck costing, receive each VIN on its own genuine
   receipt row at the time of original receipt. Existing submitted shared rows
   are left intact; bulk LCV remains available when a cost genuinely covers them.
2. For existing **on-hand** VINs in shared rows, consider an explicitly identified
   native Stock Reconciliation valuation workflow, with unchanged quantities and
   the selected serial only. The tested mode is a supported native mechanism,
   but it must not be labeled or linked as a Landed Cost Voucher.
3. Before integrating that second route, its accounting/source links, native
   permissions and idempotency, document history/links, expense account/currency
   behavior, cancellation and targeted Vehicle Master cost resolution must all
   be implemented and verified together. Current Vehicle Master derives
   `landed_cost_added` by dividing PR row charges by quantity; merely changing the
   popup's backend document would leave incorrect vehicle profitability.
4. Serial No Wise Valuation is a prerequisite for individual serial costing.
   Local vehicle items `truck` and `truck2` were both enabled during inspection.
   No setting or existing Item was changed. An item with pooled valuation cannot
   be silently switched to per-serial valuation after stock/serials already exist.

## Focused checks and changed files

Three new integration tests in
`an_truck_portal/tests/test_single_truck_cost.py` all pass:

- `test_audit_native_manual_lcv_5000_is_shared_across_ten_vins`
- `test_audit_native_selected_serial_reconciliation_preserves_other_nine`
- `test_audit_sold_vin_in_shared_row_stays_out_of_stock_and_unmodified`

```sh
bench --site dev.localhost run-tests \
  --module an_truck_portal.tests.test_single_truck_cost \
  --test test_audit_native_manual_lcv_5000_is_shared_across_ten_vins \
  --test test_audit_native_selected_serial_reconciliation_preserves_other_nine \
  --test test_audit_sold_vin_in_shared_row_stays_out_of_stock_and_unmodified
```

The fixtures are new and transactionally rolled back. Existing-document
fingerprints are compared before/after each test. Stock and GL assertions read
actual native postings; no direct stock/GL edits or core patches were used.

Changed files: this report, a pointer in `docs/single_truck_cost.md`, and the three
new tests/helper in `an_truck_portal/tests/test_single_truck_cost.py`. There are no
application runtime, popup, translation, asset, schema or configuration changes,
and no setup command, build, migration, commit or push is required for this audit.
