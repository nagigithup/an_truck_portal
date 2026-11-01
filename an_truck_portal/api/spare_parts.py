"""Standard ERPNext item catalogs for spare parts and trucks, and spare-parts stock."""

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


def _catalog_groups(catalog="spare_parts"):
	if catalog not in {"spare_parts", "trucks"}:
		frappe.throw(_("Unsupported resource"), frappe.ValidationError)
	root = SPARE_PARTS_ITEM_GROUP if catalog == "spare_parts" else frappe.db.get_single_value("AN Truck Settings", "vehicle_item_group")
	if not root:
		frappe.throw(_("Set Vehicle Item Group in AN Truck Settings before receiving vehicle items."))
	group = frappe.get_doc("Item Group", root)
	group.check_permission("read")
	if catalog == "spare_parts":
		return [frappe._dict(name=group.name, is_group=group.is_group)]
	return frappe.get_list(
		"Item Group", filters={"lft": [">=", group.lft], "rgt": ["<=", group.rgt]},
		fields=["name", "is_group"], order_by="lft asc", page_length=0,
	)


def _item_options(catalog="spare_parts"):
	_require_reference_read()
	return {
		"item_groups": [
			{"value": row.name, "label": row.name}
			for row in _catalog_groups(catalog) if not row.is_group
		],
		"uoms": [
			{"value": row.name, "label": row.name}
			for row in frappe.get_list(
				"UOM", filters={"enabled": 1}, fields=["name"], order_by="name asc", page_length=0
			)
		],
	}


@frappe.whitelist(methods=["GET"])
def list_items(search=None, page=1, page_length=20, catalog="spare_parts"):
	require_read("Item")
	page, page_length = _page_values(page, page_length)
	filters = {"item_group": ["in", [row.name for row in _catalog_groups(catalog)]]}
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
def get_item_form(name=None, catalog="spare_parts"):
	require_read("Item")
	options = _item_options(catalog)
	if not name:
		return {
			"record": {
				"item_code": "",
				"item_name": "",
				"item_group": options["item_groups"][0]["value"] if options["item_groups"] else "",
				"stock_uom": "Nos" if catalog == "trucks" and any(row["value"] == "Nos" for row in options["uoms"]) else "",
				"disabled": 0,
				"is_stock_item": 1,
			},
			"modified": None,
			"can_write": bool(frappe.has_permission("Item", "create")),
			**options,
		}

	doc = frappe.get_doc("Item", name)
	doc.check_permission("read")
	if doc.item_group not in {row.name for row in _catalog_groups(catalog)}:
		if catalog == "trucks":
			frappe.throw(_("This item is not in the truck item group."), frappe.PermissionError)
		frappe.throw(_("This item is not in the truck spare parts item group."), frappe.PermissionError)
	return {
		"record": {fieldname: doc.get(fieldname) for fieldname in ITEM_FIELDS},
		"modified": str(doc.modified),
		"can_write": bool(frappe.has_permission("Item", "write", doc=doc)),
		**options,
	}


@frappe.whitelist(methods=["POST"])
def save_item(data, name=None, modified=None, catalog="spare_parts"):
	require_access()
	groups = {row.name for row in _catalog_groups(catalog)}
	data = frappe.parse_json(data) if isinstance(data, str) else data
	if not isinstance(data, dict) or set(data) - set(ITEM_FIELDS):
		frappe.throw(_("Unsupported field."), frappe.ValidationError)

	doc = frappe.get_doc("Item", name) if name else frappe.new_doc("Item")
	permission = "write" if name else "create"
	if not frappe.has_permission("Item", permission, doc=doc):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if name:
		doc.check_permission("read")
		if doc.item_group not in groups:
			if catalog == "trucks":
				frappe.throw(_("This item is not in the truck item group."), frappe.PermissionError)
			frappe.throw(_("This item is not in the truck spare parts item group."), frappe.PermissionError)
		if str(doc.modified) != str(modified):
			frappe.throw(_("This record changed. Reload it before saving."), frappe.TimestampMismatchError)
		if "item_code" in data and data["item_code"] != doc.item_code:
			frappe.throw(_("Item Code cannot be changed in the portal."), frappe.ValidationError)
	else:
		# Keep the exact part number as Item Code. Maintain Stock defaults to on,
		# while honoring the user's explicit choice through standard Item validation.
		if not isinstance(data.get("item_code"), str):
			frappe.throw(_("Item Code is required."), frappe.MandatoryError)
		doc.item_code = data["item_code"].strip()
		doc.is_stock_item = cint(data.get("is_stock_item", 1))
		if catalog == "trucks":
			# Truck receipts use ERPNext Serial No as the VIN identity.
			doc.has_serial_no = 1

	for fieldname in ITEM_FIELDS:
		if fieldname not in data or fieldname == "item_code":
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
	if doc.item_group not in groups:
		frappe.throw(_("Select an Item Group from this catalog."), frappe.ValidationError)
	if catalog == "trucks" and not name and not doc.is_stock_item:
		frappe.throw(_("Truck items must maintain stock and use serial numbers for VIN tracking."), frappe.ValidationError)
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
