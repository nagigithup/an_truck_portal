// Live-site customer/supplier test. PORTAL_TEST_PARTY=Supplier selects suppliers.
// Creates one unique party and deletes its test records; existing parties are not edited.
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const { chromium } = require(process.env.PORTAL_PLAYWRIGHT_PATH || "playwright");
const root = "/home/nagi/my-bench";
const origin = "http://dev.localhost:8000";
const partyType = process.env.PORTAL_TEST_PARTY || "Customer";
assert.ok(["Customer", "Supplier"].includes(partyType));
const prefix = partyType.toLowerCase(), resource = prefix + "s";
const primaryField = prefix + "_primary_address";
const partyName = `Portal address UI test ${Date.now()}`;
function python(code) {
	return execFileSync(root + "/env/bin/python", ["-c", `import frappe, json
frappe.init(site='dev.localhost', sites_path='${root}/sites')
frappe.connect()
frappe.set_user('Administrator')
${code}
frappe.destroy()`], { cwd: root + "/sites", encoding: "utf8" }).trim();
}

(async () => {
	const sid = python(`from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request
frappe.local.request = Request(EnvironBuilder(path='/').get_environ())
frappe.local.request_ip = '127.0.0.1'
from frappe.sessions import Session
s = Session(user='Administrator', user_type='System User')
frappe.db.commit()
print(s.sid)`);
	const browser = await chromium.launch({ headless: true });
	const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
	await context.addCookies([{ name: "sid", value: sid, domain: "dev.localhost", path: "/" }]);
	const page = await context.newPage();
	const errors = [];
	page.on("pageerror", error => errors.push(error.message));
	async function getDoc(doctype, name) {
		const response = await context.request.get(origin + "/api/method/frappe.client.get", { params: { doctype, name } });
		assert.equal(response.status(), 200);
		return (await response.json()).message;
	}
	async function saveDialog(dialog) {
		const response = page.waitForResponse(response => response.url().includes("an_truck.portal_parties.save_party") && response.request().method() === "POST");
		await dialog.locator(".dialog-actions").getByRole("button", { name: "Save", exact: true }).click();
		const saved = await response;
		assert.equal(saved.status(), 200, await saved.text());
		await dialog.waitFor({ state: "hidden" });
		return (await saved.json()).message;
	}
	async function openEdit() {
		const row = page.locator("#main-content tbody tr").filter({ hasText: partyName });
		await row.getByRole("button", { name: /Edit|تعديل/, exact: true }).click();
		const dialog = page.locator("dialog.national-party-dialog[open]");
		await dialog.locator(".national-address-section").waitFor();
		await page.waitForFunction(() => document.querySelector("dialog.national-party-dialog[open] .dialog-actions button:last-child")?.disabled === false);
		return dialog;
	}
	try {
		await page.addInitScript(() => { if (!localStorage.getItem("an-truck-language")) localStorage.setItem("an-truck-language", "en"); });
		await page.goto(origin + "/an-truck-portal/" + resource);
		await page.getByRole("button", { name: new RegExp("New " + partyType) }).click();
		let dialog = page.locator("dialog.national-party-dialog[open]");
		await dialog.getByLabel(new RegExp(partyType + " Name", "i")).fill(partyName);
		await dialog.getByRole("button", { name: "Save", exact: true }).waitFor();
		const labels = ["Country", "City", "District", "Street", "Building Number", "Additional Number", "Postal Code", "Short Address"];
		assert.deepEqual((await dialog.locator(".national-address-section label").allTextContents()).map(label => label.trim()), labels);
		assert.equal(await dialog.getByLabel("Country").count(), 1);
		assert.equal(await dialog.getByLabel("Country").inputValue(), "Saudi Arabia");
		await dialog.getByLabel("Country").selectOption("Saudi Arabia");
		assert.equal(await dialog.getByLabel("Billing Currency").inputValue(), "SAR");
		await dialog.getByLabel("Commercial Registration Number").fill("1010123456");
		await dialog.getByLabel("Mobile Number").fill("+966501234567");
		await dialog.getByLabel("WhatsApp Number").fill("+966501234568");
		await dialog.getByLabel("Email").fill("portal-address@example.invalid");
		const address = { City: "Riyadh", District: "Olaya", Street: "Test Street", "Building Number": "1234", "Additional Number": "5678", "Postal Code": "12345", "Short Address": "ABCD1234" };
		for (const [label, value] of Object.entries(address)) await dialog.getByLabel(label).fill(value);
		const first = await dialog.getByLabel(/Country/).boundingBox(), second = await dialog.getByLabel(/City/).boundingBox();
		assert.ok(Math.abs(first.x - second.x) > 100, "Desktop address must use two columns");
		const result = await saveDialog(dialog);
		let customer = await getDoc(partyType, result.name);
		const addressName = customer[primaryField];
		assert.ok(addressName);
		if (partyType === "Customer") assert.ok(customer.custom_additional_ids.some(row => row.type_code === "CRN" && row.value === "1010123456"));
		else {
			const crKey = Object.keys(customer).find(key => key.includes("commercial_registration_number"));
			assert.equal(customer[crKey], "1010123456");
		}
		let savedAddress = await getDoc("Address", addressName);
		const fieldMap = { Country: "country", City: "city", District: "custom_area", Street: "address_line1", "Building Number": "custom_building_number", "Additional Number": "custom_additional_number", "Postal Code": "pincode", "Short Address": "custom_short_address" };
		for (const [label, field] of Object.entries(fieldMap)) assert.equal(savedAddress[field], label === "Country" ? "Saudi Arabia" : address[label]);
		assert.ok(savedAddress.links.some(row => row.link_doctype === partyType && row.link_name === customer.name));
		dialog = await openEdit();
		for (const [label, value] of Object.entries(address)) assert.equal(await dialog.getByLabel(label).inputValue(), value);
		await dialog.getByLabel("District").fill("Al Malqa");
		await saveDialog(dialog);
		customer = await getDoc(partyType, result.name);
		assert.equal(customer[primaryField], addressName);
		savedAddress = await getDoc("Address", addressName);
		assert.equal(savedAddress.custom_area, "Al Malqa");
		const count = python(`name = frappe.db.get_value('${partyType}', {'${prefix}_name': ${JSON.stringify(partyName)}}, 'name')
print(frappe.db.count('Dynamic Link', {'parenttype': 'Address', 'link_doctype': '${partyType}', 'link_name': name}))`);
		assert.equal(count, "1");
		dialog = await openEdit();
		await dialog.getByLabel("Country").selectOption("United Arab Emirates");
		await dialog.getByLabel("Billing Currency").selectOption("USD");
		await dialog.getByLabel("Building Number").fill("12");
		await saveDialog(dialog);
		await page.evaluate(() => localStorage.setItem("an-truck-language", "ar"));
		await page.setViewportSize({ width: 390, height: 844 });
		await page.reload();
		dialog = await openEdit();
		assert.equal(await page.locator("html").getAttribute("dir"), "rtl");
		assert.equal(await dialog.getByLabel("الدولة").inputValue(), "United Arab Emirates");
		assert.equal(await dialog.getByLabel("عملة الفوترة").inputValue(), "USD");
		assert.equal(await dialog.getByLabel("الحي").inputValue(), "Al Malqa");
		const a = await dialog.getByLabel("الدولة").boundingBox(), b = await dialog.getByLabel(/المدينة/).boundingBox();
		assert.ok(Math.abs(a.x - b.x) < 2, "Mobile address must use one column");
		const header = await dialog.locator(".dialog-head").boundingBox(), footer = await dialog.locator(".dialog-actions").boundingBox();
		await dialog.locator(".dialog-body").evaluate(body => { body.scrollTop = body.scrollHeight; });
		const scrolledHeader = await dialog.locator(".dialog-head").boundingBox(), scrolledFooter = await dialog.locator(".dialog-actions").boundingBox();
		assert.equal(header.y, scrolledHeader.y);
		assert.equal(footer.y, scrolledFooter.y);
		assert.ok(header.y >= 0 && footer.y + footer.height <= 844);
		await dialog.getByLabel("الدولة").selectOption("Saudi Arabia");
		await dialog.getByLabel("رقم المبنى").fill("12");
		await dialog.getByLabel("الرقم الإضافي").fill("A-7");
		await dialog.getByLabel("الرمز البريدي").fill("123");
		await dialog.getByLabel("العنوان المختصر").fill("MY ADDRESS");
		const unrestrictedSave = page.waitForResponse(response => response.url().includes("an_truck.portal_parties.save_party") && response.request().method() === "POST");
		await dialog.locator(".dialog-actions").getByRole("button", { name: "حفظ", exact: true }).click();
		assert.equal((await unrestrictedSave).status(), 200);
		await dialog.waitFor({ state: "hidden" });
		savedAddress = await getDoc("Address", addressName);
		assert.equal(savedAddress.custom_building_number, "12");
		assert.equal(savedAddress.custom_additional_number, "A-7");
		assert.equal(savedAddress.pincode, "123");
		assert.equal(savedAddress.custom_short_address, "MY ADDRESS");
		await page.screenshot({ path: `/tmp/an-truck-${prefix}-national-address-mobile.png` });
		assert.deepEqual(errors, []);
		console.log(JSON.stringify({ partyType, createAndERPNextMapping: "passed", editAndReload: "passed", duplicateAddressCount: 1, desktopTwoColumns: "passed", arabicRTLAndMobileSingleColumn: "passed", fixedHeaderFooter: "passed", unrestrictedNationalAddressValues: "passed", pageErrors: errors }));
	} finally {
		await context.request.get(origin + "/api/method/logout");
		await browser.close();
		const cleaned = python(`names = frappe.get_all('${partyType}', filters={'${prefix}_name': ${JSON.stringify(partyName)}}, pluck='name')
assert len(names) <= 1
for name in names:
    if '${partyType}' == 'Customer' and frappe.db.exists('DocType', 'Wallet'):
        for wallet in frappe.get_all('Wallet', filters={'customer': name}, pluck='name'):
            frappe.delete_doc('Wallet', wallet)
    frappe.delete_doc('${partyType}', name)
frappe.db.commit()
print(json.dumps({'test_parties_removed': len(names)}))`);
		console.log(cleaned);
	}
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
