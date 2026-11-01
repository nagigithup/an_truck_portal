// Live-site form checks; POST saves are intercepted. No Item records are created.
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const { chromium } = require(process.env.PORTAL_PLAYWRIGHT_PATH || "playwright");
const root = "/home/nagi/my-bench", origin = "http://dev.localhost:8000";
const setup = `import frappe
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request
frappe.init(site='dev.localhost', sites_path='${root}/sites')
frappe.connect()
frappe.local.request = Request(EnvironBuilder(path='/').get_environ())
frappe.local.request_ip = '127.0.0.1'
from frappe.sessions import Session
session = Session(user='Administrator', user_type='System User')
frappe.db.commit()
print(session.sid)
frappe.destroy()`;

(async () => {
	const sid = execFileSync(root + "/env/bin/python", ["-c", setup], { cwd: root + "/sites", encoding: "utf8" }).trim();
	const browser = await chromium.launch({ headless: true });
	const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
	await context.addCookies([{ name: "sid", value: sid, domain: "dev.localhost", path: "/" }]);
	const page = await context.newPage(), errors = [], saves = [];
	page.on("pageerror", error => errors.push(error.message));
	await page.route("**/api/method/an_truck_portal.api.spare_parts.save_item*", route => {
		const payload = route.request().postDataJSON();
		saves.push(payload);
		return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ message: { name: payload.data.item_code } }) });
	});
	try {
		await page.addInitScript(() => { if (!localStorage.getItem("an-truck-language")) localStorage.setItem("an-truck-language", "en"); });
		await page.goto(origin + "/an-truck-portal/spare-parts");
		await page.waitForURL("**/spare-parts/items");
		await page.getByRole("button", { name: /New Item/ }).click();
		let dialog = page.locator("dialog[open]");
		await dialog.getByLabel(/Item Code/i).fill("00-UI-PART");
		await dialog.getByLabel(/Item Name/i).fill("UI part fixture");
		const stock = dialog.getByRole("checkbox", { name: "Maintain Stock", exact: true });
		assert.equal(await stock.isEnabled(), true);
		assert.equal(await stock.isChecked(), true);
		assert.equal(await dialog.getByRole("checkbox", { name: "Disabled", exact: true }).isChecked(), false);
		await stock.uncheck();
		await dialog.getByLabel(/Stock UOM/i).selectOption("Nos");
		assert.equal(await dialog.getByLabel(/Item Group/i).inputValue(), "قطع غيار الشاحنات");
		await dialog.getByRole("button", { name: "Save", exact: true }).click();
		await dialog.waitFor({ state: "hidden" });
		assert.equal(saves[0].data.is_stock_item, 0);
		assert.equal(saves[0].catalog, "spare_parts");
		await page.goto(origin + "/an-truck-portal/truck-items");
		await page.getByRole("heading", { name: "Truck Items", exact: true }).waitFor();
		await page.getByRole("button", { name: /New Truck Item/ }).click();
		dialog = page.locator("dialog[open]");
		await dialog.getByLabel(/Item Code/i).fill("00-UI-TRUCK");
		await dialog.getByLabel(/Item Name/i).fill("UI truck fixture");
		assert.equal(await dialog.getByRole("checkbox", { name: "Maintain Stock", exact: true }).isChecked(), true);
		assert.notEqual(await dialog.getByLabel(/Item Group/i).inputValue(), "قطع غيار الشاحنات");
		await dialog.getByRole("checkbox", { name: "Maintain Stock", exact: true }).uncheck();
		await dialog.getByRole("button", { name: "Save", exact: true }).click();
		assert.match(await dialog.locator(".form-error").innerText(), /must maintain stock/);
		assert.equal(saves.length, 1);
		await dialog.getByRole("checkbox", { name: "Maintain Stock", exact: true }).check();
		await dialog.getByRole("button", { name: "Save", exact: true }).click();
		await dialog.waitFor({ state: "hidden" });
		assert.equal(saves[1].catalog, "trucks");
		assert.equal(saves[1].data.is_stock_item, 1);
		await page.evaluate(() => localStorage.setItem("an-truck-language", "ar"));
		await page.setViewportSize({ width: 390, height: 844 });
		await page.reload();
		await page.getByRole("button", { name: /صنف شاحنة جديد/ }).click();
		dialog = page.locator("dialog[open]");
		await page.waitForFunction(() => document.querySelector("dialog[open] .dialog-actions button:last-child")?.disabled === false);
		assert.equal(await dialog.getByRole("checkbox", { name: "الاحتفاظ بالمخزون", exact: true }).isChecked(), true);
		assert.equal(await page.locator("html").getAttribute("dir"), "rtl");
		assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
		await page.screenshot({ path: "/tmp/an-truck-truck-item-mobile.png" });
		assert.deepEqual(errors, []);
		console.log(JSON.stringify({ sparePartStockCheckbox: "enabled and correctly checked", explicitNonStockChoice: "passed", truckCatalogAndValidation: "passed", arabicMobileRTL: "passed", pageErrors: errors, itemWrites: "mocked; no Item records created" }));
	} finally {
		await context.request.get(origin + "/api/method/logout");
		await browser.close();
	}
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
