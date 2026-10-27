"""Portal endpoints for phase-one spare-parts item and stock management."""

import frappe
from frappe import _
from frappe.utils import cint, flt

from an_truck_portal.access import require_access, require_read

SPARE_PARTS_ITEM_GROUP = "قطع غيار الشاحنات"
ITEM_FIELDS = ("item_code", "item_name", "item_group", "stock_uom", "disabled", "is_stock_item")


def _page_values(page, page_length=20):
	page = max(cint(page), 1)
	page_length = min(max(cint(page_length), 1), 100)
	return page, page_length


def _require_reference_read():
	for doctype in ("Item Group", "UOM"):
		if not frappe.has_permission(doctype, "read"):
			frappe.throw(_("Not permitted to read {0}.").format(_(doctype)), frappe.PermissionError)


def _item_options():
	_require_reference_read()
	return {
		"item_groups": [
			{"value": row.name, "label": row.name}
			for row in frappe.get_list("Item Group", fields=["name"], order_by="name asc", page_length=0)
		],
		"uoms": [
			{"value": row.name, "label": row.name}
			for row in frappe.get_list(
				"UOM", filters={"enabled": 1}, fields=["name"], order_by="name asc", page_length=0
			)
		],
	}


@frappe.whitelist(methods=["GET"])
def list_items(search=None, page=1, page_length=20):
	require_read("Item")
	page, page_length = _page_values(page, page_length)
	filters = {"item_group": SPARE_PARTS_ITEM_GROUP}
	or_filters = None
	if search:
		or_filters = [
			["Item", "item_code", "like", f"%{search}%"],
			["Item", "item_name", "like", f"%{search}%"],
		]
	rows = frappe.get_list(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "item_code", "item_name", "item_group", "stock_uom", "disabled"],
		order_by="modified desc",
		start=(page - 1) * page_length,
		page_length=page_length + 1,
	)
	for row in rows:
		row.can_write = bool(frappe.has_permission("Item", "write", row.name))
	return {"rows": rows[:page_length], "page": page, "has_more": len(rows) > page_length}


@frappe.whitelist(methods=["GET"])
def get_item_form(name=None):
	require_read("Item")
	options = _item_options()
	if not name:
		return {
			"record": {
				"item_code": "",
				"item_name": "",
				"item_group": SPARE_PARTS_ITEM_GROUP,
				"stock_uom": "",
				"disabled": 0,
				"is_stock_item": 1,
			},
			"modified": None,
			"can_write": bool(frappe.has_permission("Item", "create")),
			**options,
		}

	doc = frappe.get_doc("Item", name)
	doc.check_permission("read")
	if doc.item_group != SPARE_PARTS_ITEM_GROUP:
		frappe.throw(_("This item is not in the truck spare parts item group."), frappe.PermissionError)
	return {
		"record": {fieldname: doc.get(fieldname) for fieldname in ITEM_FIELDS},
		"modified": str(doc.modified),
		"can_write": bool(frappe.has_permission("Item", "write", doc=doc)),
		**options,
	}


@frappe.whitelist(methods=["POST"])
def save_item(data, name=None, modified=None):
	require_access()
	data = frappe.parse_json(data) if isinstance(data, str) else data
	if not isinstance(data, dict) or set(data) - set(ITEM_FIELDS):
		frappe.throw(_("Unsupported field."), frappe.ValidationError)

	doc = frappe.get_doc("Item", name) if name else frappe.new_doc("Item")
	permission = "write" if name else "create"
	if not frappe.has_permission("Item", permission, doc=doc):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if name:
		doc.check_permission("read")
		if doc.item_group != SPARE_PARTS_ITEM_GROUP:
			frappe.throw(_("This item is not in the truck spare parts item group."), frappe.PermissionError)
		if str(doc.modified) != str(modified):
			frappe.throw(_("This record changed. Reload it before saving."), frappe.TimestampMismatchError)
		if "item_code" in data and data["item_code"] != doc.item_code:
			frappe.throw(_("Item Code cannot be changed in the portal."), frappe.ValidationError)
	else:
		# Spare parts created here always use their exact part number as Item Code
		# and participate in ERPNext's standard stock ledger.
		if not isinstance(data.get("item_code"), str):
			frappe.throw(_("Item Code is required."), frappe.MandatoryError)
		doc.item_code = data["item_code"].strip()
		doc.is_stock_item = 1

	for fieldname in ITEM_FIELDS:
		if fieldname not in data or fieldname == "item_code" or (not name and fieldname == "is_stock_item"):
			continue
		value = data[fieldname]
		if not isinstance(value, (str, int, float, type(None))):
			frappe.throw(_("Unsupported field."), frappe.ValidationError)
		doc.set(fieldname, value.strip() if isinstance(value, str) else cint(value))

	if not doc.item_code:
		frappe.throw(_("Item Code is required."), frappe.MandatoryError)
	if not doc.item_name:
		frappe.throw(_("Item Name is required."), frappe.MandatoryError)
	if not doc.item_group:
		frappe.throw(_("Item Group is required."), frappe.MandatoryError)
	if not doc.stock_uom:
		frappe.throw(_("Stock UOM is required."), frappe.MandatoryError)
	if name:
		doc.save()
	else:
		# ``set_name`` keeps the Item name and Item Code identical even when the
		# site's global Item naming setting uses a naming series.
		doc.insert(set_name=doc.item_code)
	return {"name": doc.name, "modified": str(doc.modified)}


def _accessible_companies(company=None):
	if not frappe.has_permission("Company", "read"):
		frappe.throw(_("Not permitted to read Company."), frappe.PermissionError)
	filters = {"name": company} if company else None
	companies = frappe.get_list("Company", filters=filters, pluck="name", page_length=0)
	if company and company not in companies:
		frappe.throw(_("You are not permitted to access this Company."), frappe.PermissionError)
	return companies


def _accessible_warehouses(company=None):
	if not frappe.has_permission("Warehouse", "read"):
		frappe.throw(_("Not permitted to read Warehouse."), frappe.PermissionError)
	companies = _accessible_companies(company)
	if not companies:
		return []
	return frappe.get_list(
		"Warehouse",
		filters={"company": ["in", companies], "is_group": 0, "disabled": 0},
		fields=["name", "company"],
		order_by="name asc",
		page_length=0,
	)


@frappe.whitelist(methods=["GET"])
def get_stock_options(company=None):
	require_read("Bin")
	return {"warehouses": [{"value": row.name, "label": row.name} for row in _accessible_warehouses(company)]}


@frappe.whitelist(methods=["GET"])
def list_stock(search=None, company=None, warehouse=None, page=1, page_length=20):
	require_read("Bin")
	require_read("Item")
	page, page_length = _page_values(page, page_length)
	warehouses = _accessible_warehouses(company)
	warehouse_names = [row.name for row in warehouses]
	if warehouse:
		if warehouse not in warehouse_names:
			frappe.throw(_("You are not permitted to access this Warehouse."), frappe.PermissionError)
		warehouse_names = [warehouse]
	if not warehouse_names:
		return {"rows": [], "page": page, "has_more": False}

	item_filters = {"item_group": SPARE_PARTS_ITEM_GROUP}
	item_or_filters = None
	if search:
		item_or_filters = [
			["Item", "item_code", "like", f"%{search}%"],
			["Item", "item_name", "like", f"%{search}%"],
		]
	items = frappe.get_list(
		"Item",
		filters=item_filters,
		or_filters=item_or_filters,
		fields=["name", "item_code", "item_name"],
		page_length=0,
	)
	item_names = [row.name for row in items]
	if not item_names:
		return {"rows": [], "page": page, "has_more": False}

	rows = frappe.get_list(
		"Bin",
		filters={"item_code": ["in", item_names], "warehouse": ["in", warehouse_names]},
		fields=["name", "item_code", "warehouse", "actual_qty", "reserved_qty"],
		order_by="warehouse asc, item_code asc",
		start=(page - 1) * page_length,
		page_length=page_length + 1,
	)
	item_names_by_code = {row.item_code: row.item_name for row in items}
	for row in rows:
		row.item_name = item_names_by_code.get(row.item_code, row.item_code)
		row.available_qty = flt(row.actual_qty) - flt(row.reserved_qty)
	return {"rows": rows[:page_length], "page": page, "has_more": len(rows) > page_length}
