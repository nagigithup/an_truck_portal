# Financial vouchers: inspection and implementation

## Verified architecture before implementation

- Frappe 16.54.0 / ERPNext 16.53.0 on dev.localhost.
- Existing Vue portal, router, sidebar, native dialog/form controls, ConfirmDialog,
  `call` API/CSRF handling, Arabic/English dictionaries and localStorage preference.
- Portal access requires AN Truck Portal User or System Manager; accounting
  access remains standard Payment Entry read/create/write/submit/cancel/print.
- Existing invoice-specific payment dialogs already use standard Payment Entry
  controllers, party accounts and company Mode of Payment Account mappings.
  They remain available and are not replaced.
- Existing vehicle company and global default identify `alnagi` (SAR). Default
  accounts: Cash - A, Bank Account - A, Debtors - A and Creditors - A.
- Payment Entry naming series: ACC-PAY-.YYYY.-. No active Payment Entry Workflow.
- Existing Payment Entry print formats are preserved; none becomes a global default.
- Company has no configured company_logo or default_letter_head. Configure official
  branding/contact details in Company/Address/Letter Head; the existing AN Truck
  portal logo supplies the brand fallback. FBH GOLD reference images were not
  attached to this task; the requested five-row/signature structure is the design basis.

## Scope and safeguards

New configuration explicitly identifies the voucher company. Initial setup may
infer it only when the sole vehicle company matches the site's existing default;
otherwise an administrator must configure it. Every portal voucher operation and
the dedicated print format enforce this company plus document/user permissions.
No company financial defaults or existing financial documents are rewritten.

Standard Payment Entry remains the only accounting document. Persistent request
tokens on that document prevent duplicate draft creation; row locks, status checks,
and ERPNext submission/workflow validation protect posting and cancellation.
All tests use development transactions with rollback, or uniquely marked drafts
that are removed. No production transactions are posted.

## Delivered behavior

- `/an-truck-portal/vouchers`: all permitted company vouchers, six count panels,
  server-side search/date/status filters and pagination.
- `/vouchers/receipts` and `/vouchers/payments`: dedicated Receive/Pay lists and
  shared draft forms. `/vouchers/:name`: detail, edit draft, authorized submit,
  cancel, workflow actions, print preview and PDF download.
- Standard account/party controllers determine source/target currencies and FX.
  Outstanding Sales/Purchase Invoice references support multiple invoices,
  payment terms, credit notes and signed allocations. ERPNext validates amounts,
  outstanding balances, accounting periods and posting. No manual GL writes.
- Advanced existing Payment Entry children are retained on edits; editing requires
  source-reference read access. Non-invoice references cannot be added or changed
  through the simplified form. Internal transfers can be viewed/printed with a
  transfer title; they cannot be created/edited in the Receive/Pay form.
- With an active Payment Entry Workflow, standard workflow actions replace direct
  submit/cancel. Saving a draft and submitting are separate standard requests;
  failed submission leaves the saved draft available for correction.
- Browser language preference takes precedence over the portal-specific user
  default, then Arabic. The shared language switch persists both; it does not
  change User.language. Switching in an open voucher preserves entered values.
- `AN Truck Voucher` is one language-aware Payment Entry Jinja format. Portal
  preview/PDF explicitly use the portal language; Desk uses the user's configured
  language unless an explicit print override is supplied. Missing/unsupported
  language falls back to Arabic. Standard money-in-words uses actual currency and
  fractions. Company branding/contact data are resolved at print time. Standard
  print permissions and draft/cancelled print settings still apply.

## Database changes and field mapping

No new financial DocType or ledger. The setup patch adds only:

| Location | Field | Purpose |
| --- | --- | --- |
| AN Truck Settings | `voucher_company` | Explicit company for this module |
| Payment Entry | `custom_portal_voucher_request` | Hidden unique hashed request token |
| Payment Entry | `custom_portal_voucher_payload` | Hidden request payload fingerprint |

All user fields use standard Payment Entry fields: company, payment_type,
posting_date, party_type, party, mode_of_payment, paid_from/paid_to, their account
currencies, paid_amount/received_amount, source/target_exchange_rate,
reference_no/reference_date, remarks/custom_remarks and references. Receive amount
means received_amount; Pay amount means paid_amount. Currency is account-derived.
The patch adds the print format only if its name is absent; it preserves existing
formats and global defaults. It creates optional roles without assigning users.

## Permissions and configuration

| Profile | Required roles | Capabilities |
| --- | --- | --- |
| Viewer | AN Truck Portal User + AN Truck Voucher Viewer | View/print company vouchers |
| Creator | AN Truck Portal User + AN Truck Voucher Creator | View/print/create/edit drafts |
| Approver | AN Truck Portal User + existing Accounts Manager (or existing authorized accounting role) | Native submit/cancel, subject to workflow |

Optional-role grants are scoped to voucher company for Payment Entry, Company,
Account and invoice records, and to company-linked Address/Contact records.
Existing non-voucher role grants, including owner-only grants, are preserved.
Frappe User Permissions continue to apply. Customer/Supplier remain standard
shared parties. Additional supported Party Types need their native read grants.
Do not assign general accounting roles to a user intended to be a draft-only
creator: ERPNext permissions are additive.

Deployment after installing the changed app code/assets:

```sh
bench --site <site> migrate
```

The version-controlled frontend assets are included. If rebuilding from source:

```sh
cd apps/an_truck_portal/frontend
npm run build
```

Set Financial Voucher Company in AN Truck Settings explicitly on sites where it
cannot be inferred safely. Confirm party receivable/payable accounts, currencies,
exchange rates, fiscal periods and Mode of Payment company accounts. On dev,
Cash and Bank Draft are mapped; Wire Transfer/Cheque need company account mappings
before use. Configure official Company logo/Letter Head and linked company
address/contact as needed; no contact details are fabricated.

## Focused verification

Backend integration test module:

```sh
bench --site dev.localhost run-tests --module an_truck.tests.test_financial_vouchers
```

Eleven rollback-based tests cover real standard submission and balanced GL,
all four language/type print/PDF combinations, cancellation, repeated requests,
stale updates, pagination, role/company isolation, multi-invoice allocations,
over-allocation, bank references, foreign currency, workflow dispatch and long
mixed-language content. Every test compares existing Payment Entry/GL fingerprints
before and after rollback. Workflow dispatch is mocked; this site has no active
Payment Entry Workflow. Configured production workflows still require acceptance
testing against their actual transitions/roles.

Live browser smoke test (requires local Playwright, no new runtime dependency):

```sh
PORTAL_PLAYWRIGHT_PATH=/tmp/an-truck-browser-check/node_modules/playwright \
  node apps/an_truck_portal/frontend/tests/financial-vouchers.browser.cjs
```

The browser test authenticates through an isolated session, creates uniquely marked
drafts, verifies save/reopen, language retention, Arabic mobile layout, four print
previews/PDF downloads, and deletes only its own drafts with no GL. It restores
the administrator's portal preference. Artifacts are in `/tmp/an-truck-vouchers/`.

Verified on dev.localhost: 11/11 backend tests passed; all four live browser
scenarios passed with zero JavaScript page errors. Each downloaded PDF contains
one page. Arabic mobile layout and the English/Arabic PDF layouts were visually
inspected. Frontend production build and Python compilation passed, and both
repositories passed `git diff --check`. No marked browser drafts or integration
customer fixtures remain. No full migration, service restart, commit or push was
performed for verification; the new setup patch was applied directly on dev.

## Changed files for this module

Backend (`apps/an_truck`): `an_truck/financial_vouchers.py`,
`an_truck/voucher_permissions.py`, `an_truck/hooks.py`, `an_truck/patches.txt`,
`an_truck/patches/v1_0/setup_financial_vouchers.py`,
`an_truck/print_formats/an_truck_voucher.html`, `an_truck/translations/ar.csv`,
`an_truck/tests/test_financial_vouchers.py`.

Portal (`apps/an_truck_portal`): `an_truck_portal/api/vouchers.py`,
`an_truck_portal/api/preferences.py`, `an_truck_portal/api/sales.py`,
`an_truck_portal/www/an_truck_portal.py`, `frontend/src/i18n.js`,
`frontend/src/navigation.js`, `frontend/src/router.js`,
`frontend/src/locales/ar.json`, `frontend/src/locales/en.json`,
`frontend/src/components/{VoucherActions,VoucherFormDialog,LanguageSwitch,FormField,DocumentPrintDialog,TopHeader,Sidebar}.vue`,
`frontend/src/views/Vouchers.vue`, `frontend/tests/financial-vouchers.browser.cjs`,
`an_truck_portal/public/frontend/manifest.json` and its generated JS/CSS,
and this document. Earlier quotation/template changes in the working tree remain
separate work; they were not reverted or committed.
