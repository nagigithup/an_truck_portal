// Run against an isolated build: PORTAL_BUILD_DIR=/tmp/... node tests/portal.browser.cjs
// The browser exercises real Vue routing/components with deterministic API fixtures.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require(
  process.env.PORTAL_PLAYWRIGHT_PATH || "playwright",
);
const build = process.env.PORTAL_BUILD_DIR;
const sourceMode = process.env.PORTAL_SOURCE === "1";
let devServer;
if (!build && !sourceMode)
  throw Error("Set PORTAL_BUILD_DIR to an isolated Vite build directory");
const doctypes = [
  "Vehicle Import File",
  "Vehicle Master",
  "Customer",
  "Supplier",
  "Purchase Order",
  "Purchase Receipt",
  "Purchase Invoice",
  "Payment Entry",
  "Landed Cost Voucher",
  "Quotation",
  "Sales Order",
  "Sales Invoice",
  "Serial No",
  "Quality Inspection",
];
const saved = [];
const requests = [];
let lookupDelay = 0,
  documentDelay = 0,
  lookupFails = false,
  addedGroup = false;
let failList = false,
  readonly = false,
  empty = false;
function record(dt) {
  const p = dt.toLowerCase();
  return {
    [`${p}_name`]: "Al Noor Motors",
    [`${p}_type`]: "Company",
    [`${p}_group`]: "Commercial",
    ...(dt === "Customer"
      ? { territory: "Dubai" }
      : { country: "United Arab Emirates" }),
    tax_id: "10012345",
    default_currency: "AED",
    disabled: 0,
    [`${p}_details`]: "",
    contact: {
      first_name: "Ali",
      email_id: "ali@example.com",
      mobile_no: "+971501234567",
      phone: "",
    },
    address: {
      country: "United Arab Emirates",
      city: "Dubai",
      address_line1: "Industrial Road",
      address_line2: "",
      pincode: "",
    },
  };
}
function options(dt) {
  const p = dt.toLowerCase();
  return [
    { name: `${p}_name`, label: `${dt} Name`, type: "Data", required: true },
    {
      name: `${p}_type`,
      label: `${dt} Type`,
      type: "Select",
      required: true,
      options: "Company\nIndividual",
    },
    {
      name: `${p}_group`,
      label: `${dt} Group`,
      type: "Link",
      required: true,
      options: `${dt} Group`,
    },
    dt === "Customer"
      ? {
          name: "territory",
          label: "Territory",
          type: "Link",
          required: true,
          options: "Territory",
        }
      : { name: "country", label: "Country", type: "Link", options: "Country" },
    { name: "tax_id", label: "Tax ID", type: "Data" },
    {
      name: "default_currency",
      label: dt === "Supplier" ? "Billing Currency" : "Default Currency",
      type: "Link",
      options: "Currency",
    },
    { name: "disabled", label: "Disabled", type: "Check" },
    {
      name: "custom_commercial_registration_number",
      label: "Commercial Registration Number",
      type: "Data",
    },
    { name: `${p}_details`, label: `${dt} Details`, type: "Text" },
  ];
}
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  if (url.pathname.includes("/assets/")) {
    const name = path.basename(url.pathname);
    if (name === "logo.svg") {
      res.setHeader("Content-Type", "image/svg+xml");
      return res.end(
        fs.readFileSync(
          path.join(__dirname, "../../an_truck_portal/public/logo.svg"),
        ),
      );
    }
    if (sourceMode)
      return devServer.middlewares(req, res, () => {
        res.writeHead(404);
        res.end();
      });
    if (!["an-truck-portal.js", "an-truck-portal.css"].includes(name)) {
      res.writeHead(404);
      return res.end();
    }
    res.setHeader(
      "Content-Type",
      name.endsWith(".js") ? "text/javascript" : "text/css",
    );
    return res.end(fs.readFileSync(path.join(build, name)));
  }
  if (url.pathname.startsWith("/api/method/")) {
    let body = "";
    for await (const chunk of req) body += chunk;
    const args =
      req.method === "POST"
        ? JSON.parse(body)
        : Object.fromEntries(url.searchParams);
    const method = url.pathname.split(".").at(-1),
      dt = args.doctype || "Customer";
    requests.push(method);
    if (method === "get_party" && documentDelay)
      await new Promise((resolve) => setTimeout(resolve, documentDelay));
    let message;
    if (method === "get_context")
      message = {
        companies: [{ name: "AN Motors" }, { name: "Second Company" }],
        default_company: "AN Motors",
        permissions: Object.fromEntries(
          doctypes.map((dt) => [dt, { read: true, create: !readonly }]),
        ),
      };
    else if (method === "get_dashboard")
      message = {
        cards: [
          "Open Vehicle Import Files",
          "Awaiting VIN Entry",
          "Awaiting Vehicle Master Completion",
          "Vehicles Ready for Sale",
          "Open Sales Orders",
          "Unpaid Customer Invoices",
          "Unpaid Supplier Invoices",
        ].map((label) => ({ label, value: 12, state: "ready" })),
        recent_imports: [],
        vehicles: [],
      };
    else if (method === "get_options")
      message = {
        fields: options(dt),
        create: !readonly,
        linked_permissions: { contact: true, address: true },
      };
    else if (method === "get_supplier_form_options") {
      if (lookupDelay)
        await new Promise((resolve) => setTimeout(resolve, lookupDelay));
      if (lookupFails) {
        res.writeHead(500, { "Content-Type": "application/json" });
        return res.end(
          JSON.stringify({ exc_type: "RuntimeError", exc: "private failure" }),
        );
      }
      message = {
        supplier_groups: (addedGroup
          ? ["Commercial", "New ERPNext Group"]
          : ["Commercial"]
        ).map((value) => ({ value, label: value })),
        countries: ["United Arab Emirates", "Saudi Arabia"].map((value) => ({
          value,
          label: value,
        })),
        currencies: ["AED", "SAR", "USD", "CNY"].map((value) => ({
          value,
          label: value,
        })),
      };
    } else if (method === "link_options")
      message =
        args.field === "territory"
          ? ["Dubai"]
          : args.field.includes("country")
            ? ["United Arab Emirates"]
            : ["Commercial", "AED"];
    else if (method === "list_parties") {
      if (failList) {
        res.writeHead(500, { "Content-Type": "application/json" });
        return res.end(
          JSON.stringify({
            exc: "SECRET STACK TRACE",
            exc_type: "RuntimeError",
          }),
        );
      }
      message = {
        rows: empty
          ? []
          : [
              {
                ...record(dt),
                name: `${dt}-001`,
                phone: "+97141234567",
                can_write: !readonly,
              },
            ],
        has_more: Number(args.page || 1) === 1,
        page: Number(args.page || 1),
      };
    } else if (method === "get_party")
      message = {
        record: record(dt),
        modified: "2026-10-04 12:00:00",
        can_write: !readonly,
        linked_permissions: { contact: true, address: true },
      };
    else if (method === "save_party") {
      assert.equal(req.headers["x-frappe-csrf-token"], "fixture-token");
      saved.push(args);
      message = { name: `${dt}-001` };
    } else if (method === "search")
      message = [
        { doctype: "Customer", name: "Customer-001", label: "Al Noor Motors" },
        { doctype: "Supplier", name: "Supplier-001", label: "Supplier Motors" },
      ];
    else if (method === "list_records")
      message = { rows: [{ name: "EXISTING-001", status: "Draft" }] };
    else if (method === "get_record")
      message = {
        record: { name: args.name, vin: "VIN123456789" },
        desk_url: "/app",
      };
    else {
      res.writeHead(404);
      return res.end();
    }
    res.setHeader("Content-Type", "application/json");
    return res.end(JSON.stringify({ message }));
  }
  res.setHeader("Content-Type", "text/html");
  res.end(
    `<!doctype html><html lang="en" dir="ltr"><head><meta name="viewport" content="width=device-width,initial-scale=1">${sourceMode ? "" : '<link rel="stylesheet" href="/assets/an_truck_portal/frontend/an-truck-portal.css">'}</head><body><div id="an-truck-portal"></div><script>window.anTruckBoot=${JSON.stringify({ allowed: true, full_name: "Portal Tester", csrf_token: "fixture-token", lang: "en" })}</script><script type="module" src="/assets/an_truck_portal/frontend/${sourceMode ? "src/main.js" : "an-truck-portal.js"}"></script></body></html>`,
  );
});
(async () => {
  if (sourceMode) {
    process.chdir(path.resolve(__dirname, ".."));
    const { createServer } =
      await import("../node_modules/vite/dist/node/index.js");
    devServer = await createServer({
      root: path.resolve(__dirname, ".."),
      cacheDir: fs.mkdtempSync("/tmp/an-truck-vite-preview-"),
      server: { middlewareMode: true, hmr: false, watch: null },
    });
  }
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const origin = `http://127.0.0.1:${server.address().port}`,
    browser = await chromium.launch({ headless: true }),
    page = await browser.newPage({ viewport: { width: 1440, height: 1000 } }),
    errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  async function goto(route) {
    await page.goto(`${origin}/an-truck-portal${route}`);
    await page.locator(".page").waitFor();
  }
  async function noOverflow() {
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
  }
  try {
    await goto("/");
    await page.locator(".metric").last().waitFor();
    assert.equal(await page.locator(".metric").count(), 7);
    assert.equal(await page.locator(".nav-active").count(), 1);
    await page.screenshot({
      path: "/tmp/an-truck-portal-dashboard-en.png",
      fullPage: true,
    });
    await page.getByRole("button", { name: "Language", exact: true }).click();
    assert.equal(await page.locator("html").getAttribute("dir"), "rtl");
    assert.equal((await page.locator(".sidebar").boundingBox()).x, 1440 - 254);
    await noOverflow();
    await page.screenshot({
      path: "/tmp/an-truck-portal-dashboard-ar.png",
      fullPage: true,
    });
    await page.getByRole("button", { name: "اللغة", exact: true }).click();
    await goto("/customers");
    await page
      .getByRole("link", { name: "Al Noor Motors", exact: true })
      .waitFor();
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByText("Page 2", { exact: true }).waitFor();
    await page
      .getByRole("searchbox", { name: "Search", exact: true })
      .fill("Noor");
    await page.getByText("Page 1", { exact: true }).waitFor();
    await page
      .getByRole("link", { name: "+ New Customer", exact: true })
      .click();
    await page.getByLabel("Customer Name").fill("Browser Customer");
    await page.getByLabel("Customer Group").fill("Commercial");
    await page.getByLabel("Territory").fill("Dubai");
    await page.getByRole("button", { name: "Language", exact: true }).click();
    assert.equal(
      await page.getByLabel("اسم العميل").inputValue(),
      "Browser Customer",
    );
    await page.getByRole("button", { name: "اللغة", exact: true }).click();
    await page
      .getByRole("link", { name: "Cancel", exact: true })
      .first()
      .click();
    await page.getByRole("dialog").waitFor();
    await page
      .getByRole("button", { name: "Keep editing", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Save", exact: true })
      .first()
      .click();
    await page.waitForURL(/Customer-001$/);
    assert.equal(saved[0].data.customer_name, "Browser Customer");
    await goto("/suppliers/Supplier-001?edit=1");
    await page.getByLabel("Supplier Name").fill("Updated Supplier");
    await page
      .getByRole("button", { name: "Save and New", exact: true })
      .first()
      .click();
    await page.waitForURL(/suppliers\/new$/);
    assert.equal(saved[1].data.supplier_name, "Updated Supplier");
    await goto("/customers/Customer-001");
    for (let attempt = 0; attempt < 2; attempt++) {
      await page.getByRole("button", { name: "Edit", exact: true }).click();
      await page.getByLabel("Customer Name").fill(`Same-page edit ${attempt}`);
      await page
        .getByRole("button", { name: "Save", exact: true })
        .first()
        .click();
      await page.getByRole("button", { name: "Edit", exact: true }).waitFor();
      assert.equal(await page.getByLabel("Customer Name").isDisabled(), true);
    }
    await goto("/suppliers/new");
    await page.screenshot({
      path: "/tmp/an-truck-portal-supplier-form.png",
      fullPage: true,
    });
    for (const route of [
      "/import-files",
      "/vehicles",
      "/purchase-orders",
      "/purchase-receipts",
      "/purchase-invoices",
      "/supplier-payments",
      "/landed-costs",
      "/quotations",
      "/sales-orders",
      "/sales-invoices",
      "/customer-payments",
      "/serials",
      "/inspections",
    ]) {
      await goto(route);
      await page.getByText("EXISTING-001", { exact: true }).waitFor();
    }
    await goto("/customers");
    await page
      .getByRole("searchbox", {
        name: "Search VIN, file, supplier, customer...",
      })
      .fill("Noor");
    await page
      .locator(".search-results")
      .getByRole("link", { name: /Al Noor Motors/ })
      .click();
    await page.waitForURL(/customers\/Customer-001$/);
    failList = true;
    await goto("/customers");
    await page
      .getByText("Something went wrong. Please try again.", { exact: true })
      .waitFor();
    assert.equal(await page.getByText("SECRET STACK TRACE").count(), 0);
    failList = false;
    empty = true;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await page.getByText("No customers found.", { exact: true }).waitFor();
    empty = false;
    readonly = true;
    await goto("/customers");
    await page
      .getByRole("link", { name: "Al Noor Motors", exact: true })
      .waitFor();
    assert.equal(
      await page.getByRole("link", { name: "Edit", exact: true }).count(),
      0,
    );
    await goto("/customers/Customer-001?edit=1");
    assert.equal(await page.getByLabel("Customer Name").isDisabled(), true);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("button", { name: "Language", exact: true }).click();
    await noOverflow();
    await page
      .getByRole("button", { name: "فتح القائمة", exact: true })
      .click();
    assert.equal(
      await page
        .locator(".sidebar")
        .evaluate((el) => getComputedStyle(el).visibility),
      "visible",
    );
    await page.keyboard.press("Escape");
    assert.equal(
      await page
        .locator(".sidebar")
        .evaluate((el) => getComputedStyle(el).visibility),
      "hidden",
    );
    await page.screenshot({
      path: "/tmp/an-truck-portal-mobile-ar.png",
      fullPage: true,
    });
    await goto("/customers");
    await page.getByRole("table").waitFor();
    await noOverflow();
    assert.deepEqual(errors, []);
    readonly = false;
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.evaluate(() => localStorage.setItem("an-truck-language", "en"));
    // Count requests per mounted Supplier form, including after focus/change.
    requests.length = 0;
    lookupDelay = 700;
    await goto("/suppliers/Supplier-001?edit=1");
    const group = page.getByLabel("Supplier Group"),
      currency = page.getByLabel("Billing Currency"),
      country = page.getByLabel("Country", { exact: true }).first();
    await group.waitFor();
    assert.equal(await group.isDisabled(), true);
    assert.equal(await group.inputValue(), "Commercial");
    await page.waitForFunction(
      () => !document.querySelector('select[aria-busy="true"]'),
    );
    assert.equal(await group.inputValue(), "Commercial");
    assert.equal(await country.inputValue(), "United Arab Emirates");
    assert.equal(await currency.inputValue(), "AED");
    await currency.selectOption("USD");
    await currency.selectOption("AED");
    await group.focus();
    await country.focus();
    await currency.focus();
    assert.equal(
      requests.filter((method) => method === "get_supplier_form_options")
        .length,
      1,
    );
    assert.equal(
      requests.filter((method) => method === "link_options").length,
      0,
    );
    const styles = await page
      .locator(".form-section")
      .first()
      .locator("select")
      .evaluateAll((elements) =>
        elements.map((el) => {
          const s = getComputedStyle(el);
          return [
            s.height,
            s.border,
            s.borderRadius,
            s.fontFamily,
            s.direction,
          ];
        }),
      );
    assert.ok(
      styles.every(
        (style) => JSON.stringify(style) === JSON.stringify(styles[0]),
      ),
    );
    // Lookup arrives before the Supplier record; saved values still win.
    lookupDelay = 0;
    documentDelay = 400;
    requests.length = 0;
    await goto("/suppliers/Supplier-001?edit=1");
    await group.waitFor();
    assert.equal(await group.inputValue(), "Commercial");
    assert.equal(await country.inputValue(), "United Arab Emirates");
    assert.equal(await currency.inputValue(), "AED");
    documentDelay = 0;
    // Reopening fetches the new ERPNext options, never a permanent snapshot.
    addedGroup = true;
    requests.length = 0;
    await goto("/suppliers/new");
    await page.waitForFunction(() =>
      [...document.querySelectorAll("select option")].some(
        (option) => option.value === "New ERPNext Group",
      ),
    );
    assert.equal(
      requests.filter((method) => method === "get_supplier_form_options")
        .length,
      1,
    );
    lookupFails = true;
    requests.length = 0;
    await goto("/suppliers/new");
    await page
      .getByText("Unable to load reference data. Please try again.", {
        exact: true,
      })
      .waitFor();
    assert.equal(await group.isDisabled(), true);
    lookupFails = false;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await page.waitForFunction(
      () => !document.querySelector('select[aria-busy="true"]'),
    );
    assert.equal(await group.isDisabled(), false);
    assert.equal(
      requests.filter((method) => method === "get_supplier_form_options")
        .length,
      2,
    );
    console.log(
      "PASS: one Supplier lookup per mount, no per-field requests, identical select styles, both response orders preserve saved values, fresh options after reopen, visible error and single-request retry.",
    );
    const screenshots = [];
    for (const resource of ["suppliers", "customers"]) {
      for (const lang of ["en", "ar"]) {
        await page.setViewportSize({ width: 1920, height: 1080 });
        await page.evaluate(
          (lang) => localStorage.setItem("an-truck-language", lang),
          lang,
        );
        await goto(`/${resource}/new`);
        await page.locator(".form-grid").first().waitFor();
        assert.equal(
          await page.locator("html").getAttribute("dir"),
          lang === "ar" ? "rtl" : "ltr",
        );
        const grids = await page
          .locator(".form-grid")
          .evaluateAll((elements) =>
            elements.map(
              (el) =>
                getComputedStyle(el).gridTemplateColumns.split(" ").length,
            ),
          );
        assert.ok(grids.every((count) => count === 4));
        const contact = page.locator(".form-section").nth(1);
        const boxes = await contact.locator("input").evaluateAll((elements) =>
          elements.map((el) => {
            const r = el.getBoundingClientRect();
            return { x: r.x, y: r.y, height: r.height };
          }),
        );
        assert.ok(
          boxes.every((box) => box.y === boxes[0].y && box.height === 42),
        );
        assert.equal(boxes[0].x > boxes[1].x, lang === "ar");
        if (lang === "ar") {
          const labels = await page
            .locator(
              ".party-entry label, .party-entry h2, .party-entry button, .party-entry .page-actions a",
            )
            .allTextContents();
          assert.ok(
            labels.every((text) => !/[A-Za-z]/.test(text)),
            labels.join(", "),
          );
          if (resource === "suppliers")
            assert.equal(await page.getByLabel("عملة الفوترة").count(), 1);
        }
        await noOverflow();
        const shot = `/tmp/an-truck-compact-${resource}-${lang}-desktop.png`;
        await page.screenshot({ path: shot, fullPage: true });
        screenshots.push(shot);
        for (const width of [1200, 1199, 768, 767, 390]) {
          await page.setViewportSize({ width, height: 900 });
          const columns = await page
            .locator(".form-grid")
            .first()
            .evaluate(
              (el) =>
                getComputedStyle(el).gridTemplateColumns.split(" ").length,
            );
          assert.equal(columns, width >= 1200 ? 4 : width >= 768 ? 2 : 1);
          await noOverflow();
        }
        const mobile = `/tmp/an-truck-compact-${resource}-${lang}-mobile.png`;
        await page.screenshot({ path: mobile, fullPage: true });
        screenshots.push(mobile);
      }
    }
    console.log(
      "PASS: compact forms at 1920, 1200, 1199, 768, 767 and 390px; both languages, four-column alignment, RTL order and translated labels.",
    );
    console.log(screenshots.join("\n"));
    console.log(
      "PASS: dashboard, RTL/LTR, mobile drawer, existing routes, search, pagination, create/edit payloads, unsaved dialog, read-only and error/empty states.",
    );
  } finally {
    await browser.close();
    await devServer?.close();
    server.close();
  }
})().catch((error) => {
  console.error(error);
  server.close();
  devServer?.close();
  process.exitCode = 1;
});
