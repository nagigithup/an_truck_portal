"""Auditable center-reported sales and read-only monthly settlement summaries."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, nowdate

from an_truck_portal.access import require_access
from an_truck_portal.api.maintenance_centers import _center
from an_truck_portal.api.spare_parts_pricing import _generic_price, pricing_configuration
from an_truck_portal.api.spare_parts_sales import _spare_item, get_item_availability


def _assert_scope(doc, center, company):
	center_doc = _center(center)
	if doc.center_type != center_doc.doctype or doc.center != center_doc.name or doc.company != company:
		frappe.throw(_("This sales report does not belong to the selected center and company."), frappe.PermissionError)
	return center_doc


def _result(doc):
	return {
		"name": doc.name,
		"docstatus": doc.docstatus,
		"status": "Invoiced" if doc.docstatus == 1 else "Draft",
		"sales_invoice": doc.sales_invoice,
		"sales_invoice_item": doc.sales_invoice_item,
		"modified": str(doc.modified),
	}


@frappe.whitelist(methods=["GET"])
def get_report_form(center, company, report=None):
	require_access()
	center_doc = _center(center)
	warehouse = center_doc.get("custom_company_parts_warehouse")
	if not warehouse or frappe.get_cached_value("Warehouse", warehouse, "company") != company:
		frappe.throw(_("Create the center warehouse for the selected company first."), frappe.ValidationError)
	if not center_doc.get("custom_sales_customer"):
		frappe.throw(_("Link a Sales Customer to this authorized center first."), frappe.ValidationError)
	record = {"sale_date": nowdate(), "item_code": "", "quantity": 1, "notes": ""}
	modified = None
	if report:
		doc = frappe.get_doc("Center Sales Report", report)
		doc.check_permission("read")
		_assert_scope(doc, center, company)
		if doc.docstatus != 0:
			frappe.throw(_("Only a draft center sales report can be edited."), frappe.ValidationError)
		record = {
			"sale_date": doc.sale_date,
			"item_code": doc.item_code,
			"quantity": doc.quantity,
			"notes": doc.notes,
		}
		modified = str(doc.modified)
	return {
		"record": record,
		"modified": modified,
		"warehouse": warehouse,
		"customer": center_doc.custom_sales_customer,
		"items": get_item_availability(company, warehouse),
		"can_create": bool(frappe.has_permission("Center Sales Report", "create")),
		"can_write": bool(
			frappe.has_permission("Center Sales Report", "write", report) if report else True
		),
		"can_submit": bool(frappe.has_permission("Center Sales Report", "submit")),
	}


@frappe.whitelist(methods=["GET"])
def get_report_item(center, company, item_code, sale_date):
	require_access()
	center_doc = _center(center)
	warehouse = center_doc.get("custom_company_parts_warehouse")
	if not warehouse or frappe.get_cached_value("Warehouse", warehouse, "company") != company:
		frappe.throw(_("Create the center warehouse for the selected company first."), frappe.ValidationError)
	item = _spare_item(item_code)
	config = pricing_configuration()
	retail = _generic_price(item.name, config.retail, item.stock_uom, sale_date)
	supply = _generic_price(item.name, config.supply, item.stock_uom, sale_date)
	if not retail or not supply:
		frappe.throw(
			_("Retail and Supply prices are required for this item and sale date."),
			frappe.ValidationError,
		)
	actual = flt(frappe.db.get_value("Bin", {"item_code": item.name, "warehouse": warehouse}, "actual_qty"))
	reserved = flt(
		frappe.db.get_value("Bin", {"item_code": item.name, "warehouse": warehouse}, "reserved_qty")
	)
	return {
		"item_name": item.item_name,
		"stock_uom": item.stock_uom,
		"available_qty": actual - reserved,
		"currency": frappe.get_cached_value("Price List", config.supply, "currency"),
		"supply_price": flt(supply.price_list_rate),
		"retail_price": flt(retail.price_list_rate),
		"center_margin": flt(retail.price_list_rate) - flt(supply.price_list_rate),
	}


@frappe.whitelist(methods=["POST"])
def save_report(
	center,
	company,
	data=None,
	report=None,
	modified=None,
	finalize_now=0,
	idempotency_key=None,
):
	require_access()
	if not idempotency_key:
		frappe.throw(_("Unable to safely process this report. Please reopen the form and try again."))
	cache_key = f"an_truck_portal:center_sale_report:{idempotency_key}"
	if existing := frappe.cache().get_value(cache_key):
		return existing
	if not report and (
		existing_name := frappe.db.get_value("Center Sales Report", {"operation_key": idempotency_key}, "name")
	):
		return _result(frappe.get_doc("Center Sales Report", existing_name))
	center_doc = _center(center)
	data = frappe.parse_json(data) if isinstance(data, str) else frappe._dict(data or {})
	allowed = {"sale_date", "item_code", "quantity", "notes"}
	if set(data) - allowed:
		frappe.throw(_("Unsupported field."), frappe.ValidationError)
	if report:
		doc = frappe.get_doc("Center Sales Report", report, for_update=True)
		doc.check_permission("write")
		_assert_scope(doc, center, company)
		if doc.docstatus != 0:
			frappe.throw(_("Only a draft center sales report can be edited."), frappe.ValidationError)
		if str(doc.modified) != str(modified):
			frappe.throw(_("This record changed. Reload it before saving."), frappe.TimestampMismatchError)
	else:
		doc = frappe.new_doc("Center Sales Report")
		doc.check_permission("create")
		doc.center_type = center_doc.doctype
		doc.center = center_doc.name
		doc.company = company
		doc.operation_key = idempotency_key
	doc.sale_date = data.get("sale_date")
	doc.item_code = cstr(data.get("item_code")).strip()
	doc.quantity = flt(data.get("quantity"))
	doc.notes = cstr(data.get("notes")).strip()
	doc.save()
	if cint(finalize_now):
		doc.check_permission("submit")
		doc.submit()
	result = _result(doc)
	frappe.cache().set_value(cache_key, result, expires_in_sec=60 * 60)
	return result


@frappe.whitelist(methods=["POST"])
def finalize_report(center, company, report, idempotency_key=None):
	require_access()
	if not idempotency_key:
		frappe.throw(_("Unable to safely finalize this report. Please reload and try again."))
	cache_key = f"an_truck_portal:center_sale_finalize:{report}:{idempotency_key}"
	if existing := frappe.cache().get_value(cache_key):
		return existing
	doc = frappe.get_doc("Center Sales Report", report, for_update=True)
	doc.check_permission("read")
	_assert_scope(doc, center, company)
	if doc.docstatus == 1 and doc.sales_invoice:
		result = _result(doc)
		frappe.cache().set_value(cache_key, result, expires_in_sec=60 * 60)
		return result
	if doc.docstatus != 0:
		frappe.throw(_("Only a draft center sales report can be finalized."), frappe.ValidationError)
	doc.check_permission("submit")
	doc.submit()
	result = _result(doc)
	frappe.cache().set_value(cache_key, result, expires_in_sec=60 * 60)
	return result


def _allocated_by_invoice(invoice_names):
	allocated = defaultdict(float)
	if not invoice_names:
		return allocated
	for row in frappe.get_all(
		"Payment Entry Reference",
		filters={
			"reference_doctype": "Sales Invoice",
			"reference_name": ["in", invoice_names],
			"docstatus": 1,
		},
		fields=["reference_name", "allocated_amount"],
	):
		allocated[row.reference_name] += flt(row.allocated_amount)
	return allocated


def prevent_reported_invoice_cancellation(doc, method=None):
	if doc.doctype != "Sales Invoice":
		return
	if any(row.get("custom_center_sales_report") for row in doc.items):
		frappe.throw(
			_("A Sales Invoice created from a finalized center sales report cannot be cancelled."),
			frappe.ValidationError,
		)


def center_sales_data(center, company):
	center_doc = _center(center)
	if not frappe.has_permission("Center Sales Report", "read"):
		return {"reports": [], "settlements": [], "can_report_sales": False}
	rows = frappe.get_list(
		"Center Sales Report",
		filters={"center_type": center_doc.doctype, "center": center_doc.name, "company": company},
		fields=[
			"name", "sale_date", "item_code", "quantity", "stock_uom", "currency", "supply_price",
			"supply_amount", "retail_price", "retail_amount", "center_margin", "center_margin_amount",
			"notes", "sales_invoice", "sales_invoice_item", "docstatus", "modified",
		],
		order_by="sale_date desc, creation desc",
		page_length=0,
	)
	invoice_names = [row.sales_invoice for row in rows if row.docstatus == 1 and row.sales_invoice]
	invoices = {
		row.name: row
		for row in frappe.get_list(
			"Sales Invoice",
			filters={"name": ["in", invoice_names or [""]]},
			fields=[
				"name", "currency", "net_total", "total_taxes_and_charges", "grand_total",
				"outstanding_amount", "status", "docstatus",
			],
			page_length=0,
		)
	}
	allocated = _allocated_by_invoice(list(invoices))
	reports = []
	groups = {}
	for row in rows:
		invoice = invoices.get(row.sales_invoice)
		entry = {
			**row,
			"status": "Invoiced" if row.docstatus == 1 else "Draft",
			"taxes": flt(invoice.total_taxes_and_charges) if invoice else 0,
			"invoice_total": flt(invoice.grand_total) if invoice else 0,
			"allocated_payments": flt(allocated[row.sales_invoice]) if invoice else 0,
			"outstanding_amount": flt(invoice.outstanding_amount) if invoice else 0,
			"can_record_payment": bool(
				invoice
				and invoice.docstatus == 1
				and flt(invoice.outstanding_amount) > 0
				and frappe.has_permission("Payment Entry", "create")
			),
			"can_edit": bool(row.docstatus == 0 and frappe.has_permission("Center Sales Report", "write", row.name)),
			"can_finalize": bool(row.docstatus == 0 and frappe.has_permission("Center Sales Report", "submit", row.name)),
		}
		reports.append(entry)
		if not invoice or row.docstatus != 1:
			continue
		month = cstr(row.sale_date)[:7]
		group = groups.setdefault(
			month,
			{
				"month": month, "currency": row.currency, "report_count": 0, "invoice_count": 0,
				"sold_quantity": 0, "supply_amount": 0, "retail_amount": 0, "center_margin": 0,
				"taxes": 0, "invoice_total": 0, "allocated_payments": 0, "outstanding_amount": 0,
			},
		)
		group["report_count"] += 1
		group["invoice_count"] += 1
		group["sold_quantity"] += flt(row.quantity)
		group["supply_amount"] += flt(row.supply_amount)
		group["retail_amount"] += flt(row.retail_amount)
		group["center_margin"] += flt(row.center_margin_amount)
		group["taxes"] += flt(invoice.total_taxes_and_charges)
		group["invoice_total"] += flt(invoice.grand_total)
		group["allocated_payments"] += flt(allocated[row.sales_invoice])
		group["outstanding_amount"] += flt(invoice.outstanding_amount)
	return {
		"reports": reports,
		"settlements": [groups[key] for key in sorted(groups, reverse=True)],
		"can_report_sales": bool(
			center_doc.get("custom_sales_customer")
			and center_doc.get("custom_company_parts_warehouse")
			and frappe.has_permission("Center Sales Report", "create")
		),
	}
