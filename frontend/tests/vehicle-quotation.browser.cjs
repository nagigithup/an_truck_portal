// Live UI/API check. Only its uniquely marked draft quotation is created/deleted.
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const { chromium } = require(process.env.PORTAL_PLAYWRIGHT_PATH || "playwright");
const root = "/home/nagi/my-bench", origin = "http://dev.localhost:8000";
const marker = `Quotation UI test ${Date.now()}`;
function python(code) {
	return execFileSync(root + "/env/bin/python", ["-c", `import frappe,json
frappe.init(site='dev.localhost',sites_path='${root}/sites')
frappe.connect()
frappe.set_user('Administrator')
${code}
frappe.destroy()`], { cwd: root + "/sites", encoding: "utf8" }).trim();
}
(async () => {
	const session = JSON.parse(python(`from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request
frappe.local.request=Request(EnvironBuilder(path='/').get_environ())
frappe.local.request_ip='127.0.0.1'
from frappe.sessions import Session
s=Session(user='Administrator',user_type='System User')
frappe.db.commit()
print(json.dumps({'sid':s.sid,'item':frappe.db.get_value('Vehicle Master',{},'item_code')}))`));
	const browser = await chromium.launch({ headless: true });
	const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
	await context.addCookies([{ name: "sid", value: session.sid, domain: "dev.localhost", path: "/" }]);
	const page = await context.newPage(), errors = [];
	page.on("pageerror", e => errors.push(e.message));
	let name;
	try {
		await page.addInitScript(() => localStorage.setItem("an-truck-language", "en"));
		await page.goto(origin + "/an-truck-portal/quotations");
		const formResponse = page.waitForResponse(r => r.url().includes("sales.get_sales_form"));
		await page.getByRole("button", { name: "+ Create Quotation", exact: true }).click();
		const sourceResponse = await formResponse;
		assert.equal(sourceResponse.status(), 200, await sourceResponse.text());
		const source = (await sourceResponse.json()).message;
		assert.ok(source.customers?.length, "The form must load customer choices");
		const dialog = page.getByRole("dialog", { name: "Create Quotation", exact: true });
		await dialog.getByLabel(/^Customer/).locator("option").nth(1).waitFor({ state: "attached" });
		const customer = await dialog.getByLabel(/^Customer/).locator("option").nth(1).getAttribute("value");
		await dialog.getByLabel(/^Customer/).selectOption(customer);
		await dialog.getByLabel(/^Item code$/i).fill(session.item);
		await dialog.getByLabel(/^Item code$/i).dispatchEvent("change");
		await dialog.getByLabel("Specification Template / Configuration").waitFor();
		await dialog.getByLabel("Vehicle Warranty Terms", { exact: true }).fill("Quotation-specific warranty");
		await dialog.getByLabel("Vehicle Delivery Conditions", { exact: true }).fill("Agreed delivery terms");
		await dialog.getByLabel("Notes", { exact: true }).fill(marker);
		await dialog.getByLabel("Quantity", { exact: true }).fill("2");
		await dialog.getByLabel("Rate", { exact: true }).fill("100");
		const saved = page.waitForResponse(r => r.url().includes("sales.create_sales_document") && r.request().method() === "POST", { timeout: 15000 }).catch(() => null);
		await dialog.getByRole("button", { name: /^Save draft$/i }).click({ timeout: 10000 });
		const response = await saved;
		assert.ok(response, `Save request missing: ${await dialog.locator('.form-error').allTextContents()}`);
		assert.equal(response.status(), 200, await response.text());
		name = (await response.json()).message.name;
		const persisted = await context.request.get(origin + "/api/method/an_truck_portal.api.sales.get_sales_document", { params: { doctype: "Quotation", document: name } });
		assert.equal(persisted.status(), 200);
		assert.equal((await persisted.json()).message.items[0].rate, 100, "A delayed price response must preserve the manually entered rate");
		await page.goto(origin + "/an-truck-portal/quotations/" + encodeURIComponent(name));
		await page.getByRole("button", { name: "Edit Quotation", exact: true }).click();
		const edit = page.getByRole("dialog", { name: "Edit Quotation", exact: true });
		await edit.getByLabel("Notes", { exact: true }).waitFor();
		await page.waitForFunction(marker => document.querySelector('dialog[open] textarea')?.value === marker, marker);
		assert.equal(await edit.getByLabel("Vehicle Warranty Terms", { exact: true }).inputValue(), "Quotation-specific warranty");
		assert.equal(await edit.getByLabel("VIN / Chassis Number", { exact: true }).inputValue(), "");
		await edit.getByRole("button", { name: "Cancel", exact: true }).click();
		await page.getByRole("button", { name: "Print", exact: true }).click();
		const print = page.getByRole("dialog", { name: /Print/ });
		await page.waitForFunction(() => [...document.querySelectorAll('dialog[open] select option')].some(o => o.value === 'AN Truck - Unified Vehicle Quotation'));
		assert.equal(await print.locator("select").inputValue(), "AN Truck - Unified Vehicle Quotation");
		await print.getByRole("button", { name: "Close", exact: true }).click();
		await page.addInitScript(() => localStorage.setItem("an-truck-language", "ar"));
		await page.setViewportSize({ width: 390, height: 844 });
		await page.goto(origin + "/an-truck-portal/quotations/" + encodeURIComponent(name));
		await page.getByRole("button", { name: "تعديل عرض السعر", exact: true }).click();
		await page.getByRole("dialog", { name: "تعديل عرض السعر", exact: true }).getByLabel("قالب المواصفات / التكوين").waitFor();
		assert.equal(await page.locator("html").getAttribute("dir"), "rtl");
		assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
		await page.screenshot({ path: "/tmp/an-truck-quotation-mobile.png" });
		await page.setViewportSize({ width: 1440, height: 1000 });
		await page.goto(origin + "/app/quotation/" + encodeURIComponent(name));
		await page.waitForFunction(() => window.cur_frm?.doctype === "Quotation" && cur_frm.fields_dict.items);
		assert.equal(await page.evaluate(() => frappe.meta.get_docfield("Quotation Item", "custom_vehicle_specification_template", cur_frm.doc.name).options), "Vehicle Specification Template");
		await page.locator(".custom-actions button").filter({ hasText: /Refresh Quotation Specifications|تحديث مواصفات عرض السعر/ }).first().waitFor();
		assert.deepEqual(errors, []);
		console.log(JSON.stringify({ portalCreateWithoutVIN: "passed", editReload: "passed", unifiedPrintSelection: "passed", arabicMobileRTL: "passed", deskFieldsAndRefresh: "passed", pageErrors: errors }));
	} catch (e) {
		console.error("Visible form errors:", await page.locator(".form-error").allTextContents());
		console.error("Browser errors:", errors);
		await page.screenshot({ path: "/tmp/an-truck-quotation-test-failure.png" });
		throw e;
	} finally {
		try { if (name) python(`frappe.in_test=True
doc=frappe.get_doc('Quotation',${JSON.stringify(name)})
assert doc.docstatus==0 and doc.get('custom_vehicle_quotation_notes')==${JSON.stringify(marker)}
frappe.delete_doc('Quotation',doc.name)
frappe.db.commit()`); }
		finally {
			await context.request.get(origin + "/api/method/logout").catch(() => {});
			await browser.close();
		}
	}
})().catch(e => { console.error(e.stack); process.exitCode = 1; });
