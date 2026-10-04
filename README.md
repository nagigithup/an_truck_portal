# AN Truck Portal

Modern Vue 3 operational portal for the existing `an_truck` and ERPNext data model.

- URL: `/an-truck-portal`
- Entry role: `AN Truck Portal User` (System Manager is also allowed)
- Underlying DocType permissions and User Permissions remain authoritative.
- Arabic and English are supported with automatic RTL/LTR.

### Portal design refactor

The existing application and `/an-truck-portal` routes remain in place. The shared
shell uses the navy/gold design system in `frontend/src/theme.css`. Reusable layout,
table and form components live in `frontend/src/components`. English and Arabic
catalogues live in `frontend/src/locales`; `i18n.js` extends the existing `__()`
interface and persists the chosen language locally without reloading forms.

Customers and Suppliers use dedicated list, view, create and edit screens. Their
permission-checked APIs live in `an_truck.portal_parties`, and save standard ERPNext
parties, linked Contacts and Addresses. Company selection is retained; standard
Customer/Supplier masters are shared, with User Permissions authoritative. Other
document screens retain their existing integrations and await later page migrations.
The existing search endpoint delegates to `an_truck.portal_search` so its URL stays
compatible while company filtering is enforced in the backend application.

The forms show commercial registration only when a supported existing field is
present. Shared Contacts/Addresses must be edited in Desk to avoid changing other
parties unintentionally. Secondary contact channels are preserved. Existing ERPNext
permissions for Customer/Supplier, Contact, Address and linked master data are required;
the portal role alone does not grant business-document access.

Review without publishing assets:

```bash
npm --prefix frontend run build -- --outDir /tmp/an-truck-portal-review-build --emptyOutDir false
PORTAL_BUILD_DIR=/tmp/an-truck-portal-review-build node frontend/tests/portal.browser.cjs
bench --site dev.localhost run-tests --module an_truck.tests.test_portal_parties
```

The browser test requires Playwright and Chromium; `PORTAL_PLAYWRIGHT_PATH` can point
to an existing Playwright installation. It uses deterministic API fixtures, checks
both directions and mobile layouts, and writes screenshots to `/tmp`. Backend tests
exercise real ERPNext documents inside rolled-back transactions. Publishing the
normal build output, migrations, committing and deployment are separate steps.

Build and install:

```bash
npm --prefix frontend install
npm --prefix frontend run build
bench --site dev.localhost install-app an_truck_portal
bench --site dev.localhost migrate
```

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app an_truck_portal
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/an_truck_portal
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
