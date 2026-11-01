// Focused UI checks against dev.localhost. Saved-template responses are fixtures;
// no documents are saved by this browser test. API integrity has transactional tests.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { execFileSync } = require("node:child_process");
const { chromium } = require(process.env.PORTAL_PLAYWRIGHT_PATH || "playwright");
const root = "/home/nagi/my-bench";
const origin = "http://dev.localhost:8000";
const setup = `import json, frappe
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request
frappe.init(site='dev.localhost', sites_path='${root}/sites')
frappe.connect()
frappe.local.request = Request(EnvironBuilder(path='/').get_environ())
frappe.local.request_ip = '127.0.0.1'
from frappe.sessions import Session
s = Session(user='Administrator', user_type='System User')
frappe.db.commit()
print(json.dumps({'sid': s.sid, 'vehicle': frappe.db.get_value('Vehicle Master', {}, 'name')}))
frappe.destroy()`;

(async () => {
	const session = JSON.parse(execFileSync(root + "/env/bin/python", ["-c", setup], { cwd: root + "/sites", encoding: "utf8" }).trim());
	const browser = await chromium.launch({ headless: true });
	const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
	await context.addCookies([{ name: "sid", value: session.sid, domain: "dev.localhost", path: "/" }]);
	const page = await context.newPage();
	const errors = [];
	page.on("pageerror", error => errors.push(error.message));
	const template = "UI-Specification-R1";
	const vehicle = { name: session.vehicle, vin: session.vehicle, color: "White", vehicle_status: "Received", engine_number: "ENGINE-1", receipt_date: "2026-11-01", company: "alnagi" };
	const requests = [];
	let fixtures = false;
	const api = "an_truck.an_truck.doctype.vehicle_specification_template.vehicle_specification_template.";
	await page.route("**/api/method/**", async route => {
		const url = new URL(route.request().url());
		const method = url.pathname.split("/api/method/")[1];
		let params = Object.fromEntries(url.searchParams);
		if (route.request().method() === "POST") {
			try { params = { ...params, ...JSON.parse(route.request().postData() || "{}") }; }
			catch { params = { ...params, ...Object.fromEntries(new URLSearchParams(route.request().postData() || "")) }; }
		}
		let result;
		if (fixtures && method.endsWith("specifications.list_templates")) result = { rows: [{ name: template, template_name: "UI Specification", revision: 1, status: "Published", active: 1 }], can_create: true, has_more: false };
		else if (fixtures && method.endsWith("specifications.get_template")) result = { name: template, status: "Published", can_write: false, can_create: false, linked_count: 21, sections: [] };
		else if ((fixtures && method.endsWith("specifications.get_linked_vehicles")) || method === api + "get_linked_vehicles") {
			requests.push(params);
			const filtered = !!params.search || !!params.status;
			result = { rows: filtered || Number(params.page || 1) > 1 ? [vehicle] : Array.from({ length: 20 }, (_, index) => ({ ...vehicle, name: index ? "UI-" + index : session.vehicle })), total: filtered ? 1 : 21, page: Number(params.page || 1), page_length: 20, has_more: !filtered && Number(params.page || 1) === 1, statuses: ["Received", "Sold"] };
		} else if (method === api + "get_linked_vehicle_count") result = 21;
		if (result !== undefined) return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ message: result }) });
		return route.continue();
	});
	try {
		await page.addInitScript(() => localStorage.setItem("an-truck-language", "en"));
		await page.goto(origin + "/an-truck-portal/specification-templates");
		await page.getByRole("heading", { name: "Vehicle Specification Templates", exact: true }).waitFor();
		await page.getByRole("button", { name: "New Specification Template", exact: true }).click();
		await page.locator("dialog[open]").waitFor();
		await page.getByLabel(/Template Name/).waitFor();
		await page.locator("dialog[open] .dialog-actions").getByRole("button", { name: "Close", exact: true }).click();
		fixtures = true;
		await page.reload();
		await page.getByRole("button", { name: "View", exact: true }).click();
		await page.getByRole("button", { name: "View Linked Vehicles (21)", exact: true }).click();
		let modal = page.getByRole("dialog", { name: "Linked Vehicles", exact: true });
		await modal.getByRole("button", { name: "Next", exact: true }).click();
		await page.waitForTimeout(350);
		assert.equal(String(requests.at(-1).page), "2");
		await modal.getByRole("textbox").fill("ENGINE-1");
		await page.waitForTimeout(600);
		assert.equal(requests.at(-1).search, "ENGINE-1");
		await modal.getByRole("combobox").selectOption("Received");
		await page.waitForTimeout(600);
		assert.equal(requests.at(-1).status, "Received");
		await modal.getByRole("link", { name: "View Vehicle", exact: true }).first().click();
		await page.waitForURL("**/vehicles/**");
		await page.getByRole("heading", { name: session.vehicle, exact: true }).waitFor();
		await page.addInitScript(() => localStorage.setItem("an-truck-language", "ar"));
		await page.setViewportSize({ width: 390, height: 844 });
		await page.goto(origin + "/an-truck-portal/specification-templates");
		await page.getByRole("button", { name: "عرض", exact: true }).click();
		await page.getByRole("button", { name: "عرض المركبات المرتبطة (21)", exact: true }).click();
		await page.getByRole("dialog", { name: "المركبات المرتبطة", exact: true }).waitFor();
		assert.equal(await page.locator("html").getAttribute("dir"), "rtl");
		assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
		await page.screenshot({ path: "/tmp/an-truck-linked-vehicles-mobile.png" });
		await page.setViewportSize({ width: 1440, height: 1000 });
		await page.goto(origin + "/app/vehicle-specification-template/new-vehicle-specification-template-ui-check");
		await page.waitForFunction(() => window.cur_frm?.doctype === "Vehicle Specification Template");
		await page.evaluate(async () => {
			cur_frm.doc.__islocal = 0;
			cur_frm.doc.status = "Published";
			cur_frm.doc.published_on = "2026-11-01 12:00:00";
			await cur_frm.script_manager.trigger("refresh");
		});
		await page.locator(".custom-actions button").filter({ hasText: /View Linked Vehicles|عرض المركبات المرتبطة/ }).first().click();
		await page.locator(".modal.show .table tbody tr").first().waitFor();
		assert.ok(await page.locator(".modal.show .table tbody tr").count());
		await page.screenshot({ path: "/tmp/an-truck-linked-vehicles-desk.png" });
		await page.locator(".modal.show [data-vehicle]").first().click();
		await page.waitForFunction(name => window.cur_frm?.doctype === "Vehicle Master" && cur_frm.docname === name, session.vehicle);
		console.log(JSON.stringify({ portalDesktop: "passed", portalMobileArabicRTL: "passed", searchAndStatusAndPagination: "passed", vehicleNavigation: "passed", deskModalAndVehicleNavigation: "passed", pageErrors: errors }));
		assert.deepEqual(errors, []);
	} finally {
		await context.request.get(origin + "/api/method/logout");
		await browser.close();
	}
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
