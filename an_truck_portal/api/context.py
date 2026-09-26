import frappe
from frappe.utils import now

from an_truck_portal.access import require_access


@frappe.whitelist()
def get_context():
	require_access()
	companies = frappe.get_list("Company", fields=["name", "default_currency"], order_by="name") if frappe.has_permission("Company", "read") else []
	permissions = {dt: {"read": frappe.has_permission(dt, "read"), "create": frappe.has_permission(dt, "create")} for dt in
		("Vehicle Import File", "Vehicle Master", "Supplier", "Purchase Order", "Purchase Receipt", "Purchase Invoice", "Payment Entry", "Landed Cost Voucher", "Customer", "Quotation", "Sales Order", "Sales Invoice", "Quality Inspection", "Serial No") if frappe.db.exists("DocType", dt)}
	return {"companies": companies, "default_company": frappe.defaults.get_user_default("Company"), "permissions": permissions, "server_time": now()}
