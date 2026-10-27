"""Maintenance centers and their standard ERPNext stock movements."""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, nowdate

from an_truck_portal.access import require_access, require_read
from an_truck_portal.api.spare_parts import SPARE_PARTS_ITEM_GROUP, _accessible_warehouses
from an_truck_portal.api.spare_parts_sales import _spare_item, _warehouse

AUTH_CENTER_TYPES = {"Warranty Provider", "Warranty Provider Branch"}


def _center_reference(doc):
	return f"{doc.doctype}::{doc.name}"


def _center(reference, permission="read"):
	center_type, separator, name = cstr(reference).partition("::")
	if not separator or center_type not in AUTH_CENTER_TYPES:
		frappe.throw(_("Select an authorized warranty provider or branch."), frappe.ValidationError)
	doc = frappe.get_doc(center_type, name)
	doc.check_permission(permission)
	if not cint(doc.get("active")) or (doc.doctype == "Warranty Provider" and doc.status != "Active"):
		frappe.throw(_("This authorized center is not active."), frappe.PermissionError)
	return doc


def _center_values(doc):
	address_name = doc.get("primary_address") if doc.doctype == "Warranty Provider" else doc.get("address")
	address = frappe.get_doc("Address", address_name) if address_name and frappe.db.exists("Address", address_name) else None
	return {
		"center_name": doc.get("provider_name") or doc.get("branch_name"),
		"contact_person": doc.get("contact_person") or "",
		"mobile": doc.get("mobile") or "",
		"email": doc.get("email") or "",
		"address": address.address_line1 if address else "",
		"customer": doc.get("custom_sales_customer"),
	}


@frappe.whitelist(methods=["GET"])
def list_centers(search=None, page=1, page_length=20):
	require_access()
	page, page_length = max(cint(page), 1), min(max(cint(page_length), 1), 100)
	rows = []
	term = f"%{cstr(search).strip()[:100]}%" if search else None
	for doctype, title_field in (("Warranty Provider", "provider_name"), ("Warranty Provider Branch", "branch_name")):
		if not frappe.has_permission(doctype, "read"):
			continue
		filters = {"active": 1}
		if doctype == "Warranty Provider":
			filters["status"] = "Active"
		or_filters = [[doctype, field, "like", term] for field in (title_field, "mobile", "email")] if term else None
		for row in frappe.get_list(
			doctype,
			filters=filters,
			or_filters=or_filters,
			fields=[
				"name", f"{title_field} as customer_name", "mobile as mobile_no", "email as email_id",
				"custom_sales_customer as customer", "modified",
			],
			page_length=0,
		):
			row.center_type = doctype
			row.source_name = row.name
			row.name = f"{doctype}::{row.name}"
			row.can_write = bool(frappe.has_permission(doctype, "write", row.source_name))
			rows.append(row)
	rows.sort(key=lambda row: cstr(row.customer_name).casefold())
	start = (page - 1) * page_length
	return {"rows": rows[start:start + page_length], "page": page, "has_more": len(rows) > start + page_length}


@frappe.whitelist(methods=["GET"])
def get_form(name=None, company=None):
	require_access()
	if not name:
		frappe.throw(_("Select an authorized warranty provider or branch."), frappe.MandatoryError)
	doc = _center(name)
	return {
		"record": _center_values(doc),
		"modified": str(doc.modified),
		"can_write": bool(doc.has_permission("write")),
		"customers": frappe.get_list("Customer", filters={"disabled": 0}, fields=["name", "customer_name"], order_by="customer_name asc", page_length=500),
	}


@frappe.whitelist(methods=["POST"])
def save_center(data=None, name=None, modified=None, company=None):
	require_access()
	data = frappe.parse_json(data) if isinstance(data, str) else (data or {})
	allowed = {"customer"}
	if not isinstance(data, dict) or set(data) - allowed:
		frappe.throw(_("Unsupported field."), frappe.ValidationError)
	doc = _center(name, "write")
	if str(doc.modified) != str(modified):
		frappe.throw(_("This record changed. Reload it before saving."), frappe.TimestampMismatchError)
	customer = cstr(data.get("customer")).strip()
	if customer:
		frappe.get_doc("Customer", customer).check_permission("read")
	doc.custom_sales_customer = customer or None
	doc.save()
	return {"name": _center_reference(doc), "modified": str(doc.modified)}


@frappe.whitelist(methods=["POST"])
def create_warehouse(center, company, warehouse_name, parent_warehouse):
	require_access()
	doc = _center(center, "write")
	if doc.custom_company_parts_warehouse:
		frappe.throw(_("This center already has a dedicated warehouse."), frappe.ValidationError)
	if not frappe.has_permission("Warehouse", "create"):
		frappe.throw(_("Not permitted to create Warehouse."), frappe.PermissionError)
	parent = frappe.get_doc("Warehouse", parent_warehouse)
	parent.check_permission("read")
	if parent.company != company or not parent.is_group:
		frappe.throw(_("Select a group warehouse for this company."), frappe.ValidationError)
	warehouse = frappe.new_doc("Warehouse")
	warehouse.warehouse_name = cstr(warehouse_name).strip()
	warehouse.parent_warehouse = parent.name
	warehouse.company = company
	warehouse.is_group = 0
	warehouse.insert()
	doc.db_set("custom_company_parts_warehouse", warehouse.name, update_modified=True)
	return {"name": warehouse.name}


@frappe.whitelist(methods=["GET"])
def get_warehouse_setup_options(center, company):
	doc = _center(center)
	if not company:
		frappe.throw(_("Company is required."), frappe.MandatoryError)
	frappe.get_doc("Company", company).check_permission("read")
	if not frappe.has_permission("Warehouse", "read"):
		frappe.throw(_("Not permitted to read Warehouse."), frappe.PermissionError)
	groups = frappe.get_list(
		"Warehouse",
		filters={"company": company, "is_group": 1, "disabled": 0},
		fields=["name"],
		order_by="name asc",
		page_length=0,
	)
	return {
		"warehouse_name": f"{_center_values(doc)['center_name']} Parts",
		"parent_warehouses": [{"value": row.name, "label": row.name} for row in groups],
	}


@frappe.whitelist(methods=["GET"])
def get_transfer_form(center, company):
	doc = _center(center)
	if not company:
		frappe.throw(_("Company is required."), frappe.MandatoryError)
	center_warehouse = doc.custom_company_parts_warehouse
	if not center_warehouse:
		frappe.throw(_("Create the center warehouse before transferring stock."), frappe.ValidationError)
	warehouses = _accessible_warehouses(company)
	groups = frappe.get_list(
		"Warehouse",
		filters={"company": company, "is_group": 1, "disabled": 0},
		fields=["name"],
		order_by="name asc",
		page_length=0,
	)
	return {
		"center_warehouse": center_warehouse,
		"posting_date": nowdate(),
		"warehouses": [
			{"value": row.name, "label": row.name} for row in warehouses if row.name != center_warehouse
		],
		"parent_warehouses": [{"value": row.name, "label": row.name} for row in groups],
	}


@frappe.whitelist(methods=["POST"])
def create_transfer(center, company, direction, data=None, submit_now=0, idempotency_key=None):
	require_access()
	if not company:
		frappe.throw(_("Company is required."), frappe.MandatoryError)
	if not frappe.has_permission("Stock Entry", "create"):
		frappe.throw(_("Not permitted to create Stock Entry."), frappe.PermissionError)
	if direction not in {"supply", "return"}:
		frappe.throw(_("Unsupported transfer direction."), frappe.ValidationError)
	if not idempotency_key:
		frappe.throw(_("Unable to safely process this document. Please reopen the form and try again."))
	cache_key = f"an_truck_portal:center_transfer:{idempotency_key}"
	if existing := frappe.cache().get_value(cache_key):
		return existing
	center_doc = _center(center)
	center_warehouse = center_doc.custom_company_parts_warehouse
	data = frappe.parse_json(data) if isinstance(data, str) else frappe._dict(data or {})
	other = _warehouse(company, data.other_warehouse)
	source, target = (other, center_warehouse) if direction == "supply" else (center_warehouse, other)
	if not source or not target or source == target:
		frappe.throw(_("Select different source and target warehouses."), frappe.ValidationError)
	doc = frappe.new_doc("Stock Entry")
	doc.company = company
	doc.stock_entry_type = "Material Transfer"
	doc.posting_date = data.posting_date or nowdate()
	doc.remarks = cstr(data.get("notes")).strip()
	for value in data.get("items") or []:
		row = frappe._dict(value)
		item = _spare_item(row.item_code)
		if flt(row.qty) <= 0:
			frappe.throw(_("Quantity must be greater than zero."), frappe.ValidationError)
		doc.append(
			"items",
			{
				"item_code": item.name,
				"qty": flt(row.qty),
				"uom": item.stock_uom,
				"stock_uom": item.stock_uom,
				"s_warehouse": source,
				"t_warehouse": target,
			},
		)
	if not doc.items:
		frappe.throw(_("Select at least one item."), frappe.MandatoryError)
	doc.insert()
	if cint(submit_now):
		doc.submit()
	result = {
		"name": doc.name,
		"docstatus": doc.docstatus,
		"status": "Submitted" if doc.docstatus == 1 else "Draft",
	}
	frappe.cache().set_value(cache_key, result, expires_in_sec=60 * 60)
	return result


@frappe.whitelist(methods=["POST"])
def submit_transfer(center, document):
	require_access()
	center_doc = _center(center)
	doc = frappe.get_doc("Stock Entry", document, for_update=True)
	doc.check_permission("write")
	if doc.docstatus != 0 or doc.stock_entry_type != "Material Transfer":
		frappe.throw(_("Only a draft Material Transfer can be submitted."), frappe.ValidationError)
	warehouse = center_doc.custom_company_parts_warehouse
	if not warehouse or not any(
		row.s_warehouse == warehouse or row.t_warehouse == warehouse for row in doc.items
	):
		frappe.throw(
			_("This Stock Entry does not belong to the maintenance center."),
			frappe.PermissionError,
		)
	doc.submit()
	return {"name": doc.name, "docstatus": doc.docstatus, "status": "Submitted"}


@frappe.whitelist(methods=["GET"])
def get_center(name, company=None):
	doc = _center(name)
	if not company:
		frappe.throw(_("Select a company from the header."), frappe.MandatoryError)
	frappe.get_doc("Company", company).check_permission("read")
	customer = doc.get("custom_sales_customer")
	if not customer:
		return {
			"center": {"name": _center_reference(doc), "source_name": doc.name, "center_type": doc.doctype, **_center_values(doc)},
			"invoices": [], "credit_notes": [], "payments": [], "monthly_accounts": [],
			"summary": {"invoiced": 0, "credit_notes": 0, "allocated_payments": 0, "outstanding": 0, "currency": frappe.get_cached_value("Company", company, "default_currency")},
			"summaries": [],
		}
	if not frappe.has_permission("Sales Invoice", "read"):
		frappe.throw(_("Not permitted to read Sales Invoice."), frappe.PermissionError)

	candidates = frappe.get_list(
		"Sales Invoice",
		filters={"company": company, "customer": customer, "docstatus": ["<", 2]},
		fields=["name", "customer", "customer_name", "posting_date", "currency", "selling_price_list", "net_total", "total_taxes_and_charges", "grand_total", "outstanding_amount", "is_return", "return_against", "update_stock", "docstatus", "status"],
		order_by="posting_date desc, modified desc",
		page_length=0,
	)
	commercial = []
	for invoice in candidates:
		items = frappe.get_all("Sales Invoice Item", filters={"parent": invoice.name}, fields=["item_code", "custom_vehicle_master"])
		if items and all(
			not item.custom_vehicle_master
			and frappe.get_cached_value("Item", item.item_code, "item_group") == SPARE_PARTS_ITEM_GROUP
			for item in items
		):
			commercial.append(invoice)
	base_names = {row.name for row in commercial if not row.is_return}
	invoices = [row for row in commercial if not row.is_return]
	credit_notes = [row for row in commercial if row.is_return and row.return_against in base_names]

	allocations = {}
	payments = []
	if base_names and frappe.has_permission("Payment Entry", "read"):
		refs = frappe.get_all(
			"Payment Entry Reference",
			filters={"reference_doctype": "Sales Invoice", "reference_name": ["in", list(base_names)], "docstatus": 1},
			fields=["parent", "reference_name", "allocated_amount"],
		)
		payment_names = {row.parent for row in refs}
		allowed_payments = set(frappe.get_list("Payment Entry", filters={"name": ["in", list(payment_names) or [""]]}, pluck="name", page_length=0))
		for row in refs:
			if row.parent in allowed_payments:
				allocations[row.reference_name] = allocations.get(row.reference_name, 0) + flt(row.allocated_amount)
		payments = frappe.get_list(
			"Payment Entry",
			filters={"name": ["in", list(allowed_payments) or [""]]},
			fields=["name", "party", "party_name", "posting_date", "paid_from_account_currency as currency", "received_amount", "docstatus", "status"],
			order_by="posting_date desc, modified desc",
			page_length=0,
		)
		for payment in payments:
			payment.allocated_amount = sum(flt(row.allocated_amount) for row in refs if row.parent == payment.name)
	for invoice in invoices:
		invoice.allocated_payments = allocations.get(invoice.name, 0)

	monthly = {}
	def month_row(date, currency):
		key = (cstr(date)[:7], currency)
		return monthly.setdefault(key, {"month": key[0], "currency": currency, "invoice_total": 0, "credit_notes": 0, "allocated_payments": 0, "outstanding": 0})
	for invoice in invoices:
		if invoice.docstatus == 1:
			row = month_row(invoice.posting_date, invoice.currency)
			row["invoice_total"] += flt(invoice.grand_total)
			row["outstanding"] += flt(invoice.outstanding_amount)
	for note in credit_notes:
		if note.docstatus == 1:
			row = month_row(note.posting_date, note.currency)
			row["credit_notes"] += abs(flt(note.grand_total))
			row["outstanding"] += flt(note.outstanding_amount)
	for payment in payments:
		if payment.docstatus == 1:
			month_row(payment.posting_date, payment.currency)["allocated_payments"] += flt(payment.allocated_amount)

	submitted_invoices = [row for row in invoices if row.docstatus == 1]
	summaries = {}
	for invoice in submitted_invoices:
		row = summaries.setdefault(invoice.currency, {"currency": invoice.currency, "invoiced": 0, "credit_notes": 0, "allocated_payments": 0, "outstanding": 0})
		row["invoiced"] += flt(invoice.grand_total)
		row["allocated_payments"] += flt(invoice.allocated_payments)
		row["outstanding"] += flt(invoice.outstanding_amount)
	for note in credit_notes:
		if note.docstatus == 1:
			row = summaries.setdefault(note.currency, {"currency": note.currency, "invoiced": 0, "credit_notes": 0, "allocated_payments": 0, "outstanding": 0})
			row["credit_notes"] += abs(flt(note.grand_total))
			row["outstanding"] += flt(note.outstanding_amount)
	return {
		"center": {"name": _center_reference(doc), "source_name": doc.name, "center_type": doc.doctype, **_center_values(doc)},
		"invoices": invoices,
		"credit_notes": credit_notes,
		"payments": payments,
		"monthly_accounts": sorted(monthly.values(), key=lambda row: (row["month"], row["currency"]), reverse=True),
		"summaries": list(summaries.values()),
		"summary": {
			"invoiced": sum(flt(row.grand_total) for row in submitted_invoices),
			"credit_notes": sum(abs(flt(row.grand_total)) for row in credit_notes if row.docstatus == 1),
			"allocated_payments": sum(flt(row.allocated_payments) for row in payments if row.docstatus == 1),
			"outstanding": sum(flt(row.outstanding_amount) for row in submitted_invoices)
			+ sum(flt(row.outstanding_amount) for row in credit_notes if row.docstatus == 1),
			"currency": frappe.get_cached_value("Company", company, "default_currency"),
		},
	}


def _center_invoice(center_doc, company, invoice_name):
	from an_truck_portal.api.spare_parts_sales import _assert_spare_invoice

	invoice = frappe.get_doc("Sales Invoice", invoice_name)
	invoice.check_permission("read")
	if (
		invoice.company != company
		or invoice.customer != center_doc.get("custom_sales_customer")
		or invoice.docstatus != 1
		or invoice.is_return
	):
		frappe.throw(_("Select a submitted center Sales Invoice."), frappe.ValidationError)
	_assert_spare_invoice(invoice)
	return invoice


@frappe.whitelist(methods=["GET"])
def get_sales_return_form(center, company, invoice=None):
	from erpnext.controllers.sales_and_purchase_return import make_return_doc

	require_access()
	center_doc = _center(center)
	if not company:
		frappe.throw(_("Company is required."), frappe.MandatoryError)
	frappe.get_doc("Company", company).check_permission("read")
	if not center_doc.get("custom_sales_customer"):
		frappe.throw(_("Link a Sales Customer to this authorized center first."), frappe.ValidationError)
	if not frappe.has_permission("Sales Invoice", "create") or not frappe.has_permission("Sales Invoice", "submit"):
		frappe.throw(_("You need permission to create and submit Sales Invoices."), frappe.PermissionError)
	candidates = frappe.get_list(
		"Sales Invoice",
		filters={
			"company": company,
			"customer": center_doc.custom_sales_customer,
			"docstatus": 1,
			"is_return": 0,
			"update_stock": 1,
		},
		fields=["name", "posting_date", "currency", "grand_total", "outstanding_amount"],
		order_by="posting_date desc, modified desc",
		page_length=0,
	)
	eligible = []
	for row in candidates:
		try:
			_center_invoice(center_doc, company, row.name)
		except (frappe.PermissionError, frappe.ValidationError):
			continue
		eligible.append(row)
	result = {"posting_date": nowdate(), "invoices": eligible, "items": []}
	if invoice:
		source = _center_invoice(center_doc, company, invoice)
		mapped = make_return_doc("Sales Invoice", source.name)
		result["items"] = [
			{
				"source_row": row.sales_invoice_item,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"stock_uom": row.stock_uom,
				"warehouse": row.warehouse,
				"returnable_qty": abs(flt(row.qty)),
			}
			for row in mapped.items
			if flt(row.qty) < 0
		]
	return result


@frappe.whitelist(methods=["POST"])
def create_sales_return(center, company, invoice, data=None, idempotency_key=None):
	from erpnext.controllers.sales_and_purchase_return import make_return_doc

	require_access()
	if not company:
		frappe.throw(_("Company is required."), frappe.MandatoryError)
	frappe.get_doc("Company", company).check_permission("read")
	if not idempotency_key:
		frappe.throw(_("Unable to safely process this document. Please reopen the form and try again."))
	cache_key = f"an_truck_portal:center_sales_return:{frappe.session.user}:{idempotency_key}"
	if existing := frappe.cache().get_value(cache_key):
		return existing
	if not frappe.has_permission("Sales Invoice", "create") or not frappe.has_permission("Sales Invoice", "submit"):
		frappe.throw(_("You need permission to create and submit Sales Invoices."), frappe.PermissionError)
	center_doc = _center(center)
	source = _center_invoice(center_doc, company, invoice)
	data = frappe.parse_json(data) if isinstance(data, str) else frappe._dict(data or {})
	requested = {}
	for value in data.get("items") or []:
		row = frappe._dict(value)
		qty = flt(row.qty)
		if qty > 0:
			requested[cstr(row.source_row)] = qty
	if not requested:
		frappe.throw(_("Enter at least one return quantity."), frappe.MandatoryError)
	credit_note = make_return_doc("Sales Invoice", source.name)
	kept = []
	for row in credit_note.items:
		qty = requested.get(cstr(row.sales_invoice_item), 0)
		if not qty:
			continue
		if qty > abs(flt(row.qty)):
			frappe.throw(
				_("Return quantity for item {0} cannot exceed {1}.").format(row.item_code, abs(flt(row.qty))),
				frappe.ValidationError,
			)
		row.qty = -qty
		row.stock_qty = -qty * flt(row.conversion_factor or 1)
		kept.append(row)
	credit_note.set("items", kept)
	if not credit_note.items:
		frappe.throw(_("The selected quantities are no longer available to return."), frappe.ValidationError)
	credit_note.posting_date = data.get("posting_date") or nowdate()
	credit_note.remarks = cstr(data.get("notes")).strip()
	credit_note.update_stock = 1
	credit_note.run_method("calculate_taxes_and_totals")
	credit_note.insert()
	credit_note.submit()
	result = {"name": credit_note.name, "docstatus": credit_note.docstatus, "status": credit_note.status}
	frappe.cache().set_value(cache_key, result, expires_in_sec=60 * 60)
	return result
