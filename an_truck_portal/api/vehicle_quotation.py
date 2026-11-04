"""Portal-specific access boundary around the shared Quotation implementation."""
import frappe
from frappe import _

from an_truck_portal.access import require_access


@frappe.whitelist()
def template_options(item_code=None, search=""):
	require_access()
	from an_truck.vehicle_quotation import template_options as options
	return [row.name for row in options(item_code, search)]


@frappe.whitelist(methods=["POST"])
def refresh_specifications(name):
	require_access()
	from an_truck.vehicle_quotation import refresh_specifications as refresh
	return refresh(name)


@frappe.whitelist()
def item_details(item_code, customer, company, price_list=None, transaction_date=None, qty=1, currency=None):
	require_access()
	if not (frappe.has_permission("Quotation", "create") or frappe.has_permission("Quotation", "write")):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	for doctype, name in (("Item", item_code), ("Customer", customer), ("Company", company)):
		frappe.get_doc(doctype, name).check_permission("read")
	price_list = price_list or frappe.db.get_single_value("Selling Settings", "selling_price_list")
	if price_list:
		frappe.get_doc("Price List", price_list).check_permission("read")
	from erpnext.stock.get_item_details import get_item_details
	from frappe.utils import flt, nowdate
	result = get_item_details(frappe._dict({
		"doctype": "Quotation", "item_code": item_code, "customer": customer, "company": company,
		"selling_price_list": price_list, "transaction_date": transaction_date or nowdate(),
		"qty": flt(qty) or 1, "currency": currency or (frappe.db.get_value("Price List", price_list, "currency") if price_list else frappe.get_cached_value("Company", company, "default_currency")),
	}))
	return {key: result.get(key) for key in ("item_name", "description", "stock_uom", "uom", "rate", "price_list_rate", "discount_percentage")}
