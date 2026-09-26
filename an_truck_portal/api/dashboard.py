import frappe

from an_truck_portal.access import require_access


def _count(dt, filters):
	if not frappe.db.exists("DocType", dt) or not frappe.has_permission(dt, "read"):
		return {"state": "unavailable", "value": None}
	# get_list applies DocType and User Permission conditions. The bounded pluck avoids
	# exposing an unrestricted database count while keeping dashboard reads compact.
	rows = frappe.get_list(dt, filters=filters, pluck="name", limit_page_length=1001)
	return {"state": "ready", "value": len(rows), "capped": len(rows) == 1001}


@frappe.whitelist()
def get_dashboard(company=None):
	require_access()
	cf = {"company": company} if company else {}
	cards = [
		("Open Vehicle Import Files", "Vehicle Import File", {**cf, "status": ["not in", ["Completed", "Cancelled"]]}),
		("Awaiting VIN Entry", "Vehicle Import File", {**cf, "total_remaining_vehicles": [">", 0]}),
		("Awaiting Vehicle Master Completion", "Vehicle Master", {**cf, "model": ["is", "not set"]}),
		("Vehicles Ready for Sale", "Vehicle Master", {**cf, "vehicle_status": "Available"}),
		("Open Sales Orders", "Sales Order", {**cf, "docstatus": 1, "status": ["not in", ["Completed", "Closed"]]}),
		("Unpaid Customer Invoices", "Sales Invoice", {**cf, "docstatus": 1, "outstanding_amount": [">", 0]}),
		("Unpaid Supplier Invoices", "Purchase Invoice", {**cf, "docstatus": 1, "outstanding_amount": [">", 0]}),
	]
	return {"cards": [{"label": label, "doctype": dt, **_count(dt, filters)} for label, dt, filters in cards],
		"recent_imports": frappe.get_list("Vehicle Import File", filters=cf, fields=["name", "import_title", "supplier", "status", "expected_arrival_date", "modified"], order_by="modified desc", limit=8) if frappe.has_permission("Vehicle Import File", "read") else None,
		"vehicles": frappe.get_list("Vehicle Master", filters=cf, fields=["name", "vin", "item_name", "brand", "model", "vehicle_status", "vehicle_import_file"], order_by="modified desc", limit=8) if frappe.has_permission("Vehicle Master", "read") else None}
