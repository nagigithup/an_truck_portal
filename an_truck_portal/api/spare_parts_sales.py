"""Direct spare-parts Sales Invoices backed by standard ERPNext documents."""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, nowdate

from an_truck_portal.access import require_access, require_read
from an_truck_portal.api.spare_parts import SPARE_PARTS_ITEM_GROUP, _accessible_warehouses
from an_truck_portal.api.spare_parts_pricing import (
	_generic_price,
	can_manage_prices,
	pricing_configuration,
)

SALE_TYPES = {"retail", "center", "supplier"}


def _spare_item(item_code):
	doc = frappe.get_doc("Item", item_code)
	doc.check_permission("read")
	if doc.item_group != SPARE_PARTS_ITEM_GROUP or doc.disabled or not doc.is_sales_item:
		frappe.throw(_("Select an enabled truck spare-parts sales item."), frappe.ValidationError)
	return doc


def _warehouse(company, warehouse):
	allowed = {row.name for row in _accessible_warehouses(company)}
	if warehouse not in allowed:
		frappe.throw(_("You are not permitted to access this Warehouse."), frappe.PermissionError)
	return warehouse


def _tax_template(company, name):
	if not name:
		return None
	doc = frappe.get_doc("Sales Taxes and Charges Template", name)
	doc.check_permission("read")
	if doc.company != company or doc.disabled:
		frappe.throw(_("Select an enabled tax template for this company."), frappe.ValidationError)
	return doc.name


def _linked_customer_for_supplier(supplier):
	links = frappe.get_all(
		"Party Link",
		filters={"primary_role": "Supplier", "primary_party": supplier, "secondary_role": "Customer"},
		pluck="secondary_party",
	)
	links += frappe.get_all(
		"Party Link",
		filters={"secondary_role": "Supplier", "secondary_party": supplier, "primary_role": "Customer"},
		pluck="primary_party",
	)
	return links[0] if links else None


def _supply_customers():
	customers = set()
	for doctype in ("Warranty Provider", "Warranty Provider Branch"):
		customers.update(
			frappe.get_all(
				doctype,
				filters={"custom_sales_customer": ["is", "set"]},
				pluck="custom_sales_customer",
			)
		)
	for row in frappe.get_all(
		"Party Link", fields=["primary_role", "primary_party", "secondary_role", "secondary_party"]
	):
		if row.primary_role == "Supplier" and row.secondary_role == "Customer":
			customers.add(row.secondary_party)
		elif row.secondary_role == "Supplier" and row.primary_role == "Customer":
			customers.add(row.primary_party)
	return customers


def _center_doc(center_type, center):
	if center_type not in {"Warranty Provider", "Warranty Provider Branch"}:
		frappe.throw(_("Select an authorized warranty provider or branch."), frappe.ValidationError)
	doc = frappe.get_doc(center_type, center)
	doc.check_permission("read")
	if not cint(doc.get("active")) or (center_type == "Warranty Provider" and doc.status != "Active"):
		frappe.throw(_("Select an active authorized center."), frappe.ValidationError)
	return doc


def _resolve_buyer(data):
	sale_type = cstr(data.get("sale_type") or "retail")
	if sale_type not in SALE_TYPES:
		frappe.throw(_("Select a valid sale type."), frappe.ValidationError)
	config = pricing_configuration(require_supply=sale_type != "retail")
	if sale_type == "center":
		center = _center_doc(data.get("center_type"), data.get("center"))
		customer = center.get("custom_sales_customer")
		if not customer:
			frappe.throw(_("Link a Sales Customer to this authorized center first."), frappe.ValidationError)
	elif sale_type == "supplier":
		supplier = cstr(data.get("supplier")).strip()
		if not supplier:
			frappe.throw(_("Supplier is required."), frappe.MandatoryError)
		frappe.get_doc("Supplier", supplier).check_permission("read")
		customer = _linked_customer_for_supplier(supplier)
		if not customer:
			frappe.throw(_("This supplier must be linked to an existing Customer using Party Link."), frappe.ValidationError)
	else:
		customer = cstr(data.get("customer")).strip()
		if customer in _supply_customers():
			frappe.throw(
				_("Select the Center or Supplier Buyer sale type for this Customer."),
				frappe.ValidationError,
			)
	if not customer:
		frappe.throw(_("Customer is required."), frappe.MandatoryError)
	customer_doc = frappe.get_doc("Customer", customer)
	customer_doc.check_permission("read")
	if customer_doc.disabled:
		frappe.throw(_("Select an enabled Customer."), frappe.ValidationError)
	return sale_type, customer, config.supply if sale_type in {"center", "supplier"} else config.retail


def _build_invoice(data):
	data = frappe._dict(data or {})
	if not data.company:
		frappe.throw(_("Company is required."), frappe.MandatoryError)
	sale_type, customer, price_list = _resolve_buyer(data)
	frappe.get_doc("Company", data.company).check_permission("read")
	warehouse = _warehouse(data.company, data.source_warehouse)
	rows = data.get("items") or []
	if not rows:
		frappe.throw(_("Select at least one item."), frappe.MandatoryError)
	doc = frappe.new_doc("Sales Invoice")
	doc.customer = customer
	doc.company = data.company
	doc.posting_date = data.posting_date or nowdate()
	doc.update_stock = 1
	doc.set_warehouse = warehouse
	doc.selling_price_list = price_list
	doc.taxes_and_charges = _tax_template(data.company, data.get("taxes_and_charges"))
	doc.remarks = cstr(data.get("notes")).strip()
	doc.po_no = cstr(data.get("reference")).strip()
	seen = set()
	for value in rows:
		row = frappe._dict(value)
		item_code = cstr(row.item_code).strip()
		if not item_code or flt(row.qty) <= 0:
			frappe.throw(_("Enter valid item quantities."), frappe.ValidationError)
		if item_code in seen:
			frappe.throw(_("Combine duplicate item rows before saving."), frappe.ValidationError)
		seen.add(item_code)
		item = _spare_item(item_code)
		doc.append(
			"items",
			{
				"item_code": item.name,
				"item_name": item.item_name,
				"qty": flt(row.qty),
				"warehouse": warehouse,
			},
		)
	doc.run_method("set_missing_values")
	for source, target in zip(rows, doc.items, strict=True):
		if not flt(target.price_list_rate):
			frappe.throw(
				_("No {0} price is configured for item {1}.").format(price_list, target.item_code),
				frappe.ValidationError,
			)
		requested = frappe._dict(source).get("rate")
		if requested not in (None, "") and abs(flt(requested) - flt(target.price_list_rate)) > 0.000001:
			if not can_manage_prices():
				frappe.throw(_("You are not permitted to override invoice rates."), frappe.PermissionError)
			target.rate = flt(requested)
	doc.run_method("calculate_taxes_and_totals")
	doc.flags.portal_spare_parts_sale_type = sale_type
	return doc


def _assert_spare_invoice(doc):
	if doc.doctype != "Sales Invoice" or not cint(doc.update_stock) or not doc.items:
		frappe.throw(_("This is not a direct spare-parts Sales Invoice."), frappe.PermissionError)
	for row in doc.items:
		if (
			row.get("custom_vehicle_master")
			or frappe.get_cached_value("Item", row.item_code, "item_group") != SPARE_PARTS_ITEM_GROUP
		):
			frappe.throw(_("This is not a direct spare-parts Sales Invoice."), frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def get_invoice(document):
	from an_truck_portal.api.sales import get_sales_document

	require_access()
	doc = frappe.get_doc("Sales Invoice", document)
	doc.check_permission("read")
	_assert_spare_invoice(doc)
	result = get_sales_document("Sales Invoice", document)
	result["document"]["selling_price_list"] = doc.selling_price_list
	return result


@frappe.whitelist(methods=["GET"])
def get_form(company):
	require_access()
	if not company:
		frappe.throw(
			_("Select a company from the header before creating a Sales Invoice."), frappe.MandatoryError
		)
	if not frappe.has_permission("Sales Invoice", "create"):
		frappe.throw(_("Not permitted to create Sales Invoice."), frappe.PermissionError)
	warehouses = _accessible_warehouses(company)
	config = pricing_configuration(require_supply=False)
	items = frappe.get_list(
		"Item",
		filters={"item_group": SPARE_PARTS_ITEM_GROUP, "disabled": 0, "is_sales_item": 1},
		fields=["name", "item_name", "stock_uom"],
		order_by="item_name asc",
		page_length=500,
	)
	customers = frappe.get_list(
		"Customer", filters={"disabled": 0}, fields=["name", "customer_name"], order_by="customer_name asc", page_length=500
	)
	supply_customers = _supply_customers()
	customers = [row for row in customers if row.name not in supply_customers]
	center_rows = []
	for doctype, title_field in (("Warranty Provider", "provider_name"), ("Warranty Provider Branch", "branch_name")):
		if not frappe.has_permission(doctype, "read"):
			continue
		filters = {"active": 1}
		if doctype == "Warranty Provider":
			filters["status"] = "Active"
		for row in frappe.get_list(
			doctype,
			filters=filters,
			fields=["name", f"{title_field} as label", "custom_sales_customer as customer"],
			order_by=f"{title_field} asc",
			page_length=500,
		):
			if row.customer:
				row.center_type = doctype
				center_rows.append(row)
	accessible_suppliers = (
		frappe.get_list(
			"Supplier",
			filters={"disabled": 0},
			fields=["name", "supplier_name"],
			order_by="supplier_name asc",
			page_length=500,
		)
		if frappe.has_permission("Supplier", "read")
		else []
	)
	supplier_buyers = []
	for row in accessible_suppliers:
		if customer := _linked_customer_for_supplier(row.name):
			supplier_buyers.append({**row, "customer": customer})
	return {
		"company": company,
		"posting_date": nowdate(),
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"customers": customers,
		"centers": center_rows,
		"supplier_buyers": supplier_buyers,
		"retail_price_list": config.retail,
		"supply_price_list": config.supply,
		"can_override_rate": can_manage_prices(),
		"warehouses": [{"value": row.name, "label": row.name} for row in warehouses],
		"items": [
			{
				**row,
				"available_qty": flt(
					frappe.db.get_value(
						"Bin", {"item_code": row.name, "warehouse": warehouses[0].name}, "actual_qty"
					)
					if len(warehouses) == 1
					else 0
				),
			}
			for row in items
		],
		"tax_templates": frappe.get_list(
			"Sales Taxes and Charges Template",
			filters={"company": company, "disabled": 0},
			fields=["name", "title", "is_default"],
			order_by="is_default desc, title asc",
			page_length=0,
		),
	}


@frappe.whitelist(methods=["GET"])
def get_item_availability(company, warehouse, search=None, price_list=None):
	require_read("Item")
	if not company:
		frappe.throw(_("Company is required."), frappe.MandatoryError)
	_warehouse(company, warehouse)
	or_filters = None
	if search:
		term = f"%{cstr(search).strip()[:100]}%"
		or_filters = [["Item", "item_code", "like", term], ["Item", "item_name", "like", term]]
	items = frappe.get_list(
		"Item",
		filters={"item_group": SPARE_PARTS_ITEM_GROUP, "disabled": 0, "is_sales_item": 1},
		or_filters=or_filters,
		fields=["name", "item_name", "stock_uom"],
		order_by="item_name asc",
		page_length=100,
	)
	balances = {
		row.item_code: flt(row.actual_qty) - flt(row.reserved_qty)
		for row in frappe.get_list(
			"Bin",
			filters={"warehouse": warehouse, "item_code": ["in", [item.name for item in items] or [""]]},
			fields=["item_code", "actual_qty", "reserved_qty"],
			page_length=0,
		)
	}
	prices = {}
	if price_list:
		pricing_configuration(require_supply=price_list != pricing_configuration(False).retail)
		allowed_lists = set(pricing_configuration(False).values())
		if price_list not in allowed_lists:
			frappe.throw(_("Select a configured spare-parts Price List."), frappe.ValidationError)
		for item in items:
			if row := _generic_price(item.name, price_list, item.stock_uom):
				prices[item.name] = flt(row.price_list_rate)
	return [{**item, "available_qty": balances.get(item.name, 0), "price_list_rate": prices.get(item.name)} for item in items]


@frappe.whitelist(methods=["POST"])
def preview(data=None):
	require_access()
	data = frappe.parse_json(data) if isinstance(data, str) else data
	doc = _build_invoice(data)
	return {
		"net_total": doc.net_total,
		"total_taxes_and_charges": doc.total_taxes_and_charges,
		"grand_total": doc.grand_total,
		"rounded_total": doc.rounded_total,
		"taxes": [
			{"description": row.description, "rate": row.rate, "tax_amount": row.tax_amount}
			for row in doc.taxes
		],
	}


@frappe.whitelist(methods=["POST"])
def create(data=None, submit_now=0, idempotency_key=None):
	require_access()
	if not frappe.has_permission("Sales Invoice", "create"):
		frappe.throw(_("Not permitted to create Sales Invoice."), frappe.PermissionError)
	if not idempotency_key:
		frappe.throw(_("Unable to safely process this document. Please reopen the form and try again."))
	cache_key = f"an_truck_portal:spare_invoice:{idempotency_key}"
	if existing := frappe.cache().get_value(cache_key):
		return existing
	data = frappe.parse_json(data) if isinstance(data, str) else data
	doc = _build_invoice(data)
	doc.insert()
	if cint(submit_now):
		doc.submit()
	result = {"doctype": doc.doctype, "name": doc.name, "docstatus": doc.docstatus, "status": doc.status}
	frappe.cache().set_value(cache_key, result, expires_in_sec=60 * 60)
	return result


@frappe.whitelist(methods=["POST"])
def submit_invoice(document):
	require_access()
	doc = frappe.get_doc("Sales Invoice", document, for_update=True)
	doc.check_permission("write")
	_assert_spare_invoice(doc)
	if doc.docstatus != 0:
		frappe.throw(_("Only a draft Sales Invoice can be submitted."), frappe.ValidationError)
	doc.submit()
	return {"name": doc.name, "docstatus": doc.docstatus, "status": doc.status}


@frappe.whitelist(methods=["GET"])
def list_invoices(search=None, company=None, page=1, page_length=20):
	require_read("Sales Invoice")
	page, page_length = max(cint(page), 1), min(max(cint(page_length), 1), 100)
	filters = {"update_stock": 1}
	if company:
		frappe.get_doc("Company", company).check_permission("read")
		filters["company"] = company
	or_filters = None
	if search:
		term = f"%{cstr(search).strip()[:100]}%"
		or_filters = [
			["Sales Invoice", field, "like", term] for field in ("name", "customer", "customer_name")
		]
	candidates = frappe.get_list(
		"Sales Invoice",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name",
			"customer",
			"customer_name",
			"posting_date",
			"company",
			"currency",
			"selling_price_list",
			"grand_total",
			"outstanding_amount",
			"status",
			"docstatus",
		],
		order_by="posting_date desc, modified desc",
		page_length=500,
	)
	result = []
	for row in candidates:
		items = frappe.get_all(
			"Sales Invoice Item", filters={"parent": row.name}, fields=["item_code", "custom_vehicle_master"]
		)
		if items and all(
			not item.custom_vehicle_master
			and frappe.get_cached_value("Item", item.item_code, "item_group") == SPARE_PARTS_ITEM_GROUP
			for item in items
		):
			result.append(row)
	start = (page - 1) * page_length
	return {
		"rows": result[start : start + page_length],
		"page": page,
		"has_more": len(result) > start + page_length,
	}
