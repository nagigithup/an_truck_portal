import base64
import binascii
import json
from urllib.parse import quote

import frappe
from an_truck.services import CUSTOM_FIELD
from frappe import _
from frappe.handler import upload_file
from frappe.utils import cint, cstr, flt, getdate, now_datetime, nowdate

from an_truck_portal.access import require_access

SALES_DOCTYPES = {"Quotation", "Sales Order", "Sales Invoice"}
DELIVERY_ACKNOWLEDGMENT_MARKER = "AN_TRUCK_PORTAL_VEHICLE_DELIVERY_V1:"
DELIVERY_ACCESSORIES = (
	"main_key",
	"spare_key",
	"spare_tire",
	"jack",
	"tool_kit",
	"fire_extinguisher",
	"warning_triangle",
	"other",
)


def _require_sales_doctype(doctype):
	if doctype not in SALES_DOCTYPES:
		frappe.throw(_("Unsupported resource"), frappe.ValidationError)


def _files(doctype, name):
	return frappe.get_all(
		"File",
		filters={"attached_to_doctype": doctype, "attached_to_name": name, "is_folder": 0},
		fields=["name", "file_name", "file_url", "is_private"],
		order_by="creation asc",
	)


def _document_date(doc):
	return doc.get("posting_date") or doc.get("transaction_date")


def _completed_import_file(doc):
	name = doc.get(CUSTOM_FIELD)
	return bool(
		name and frappe.get_cached_value("Vehicle Import File", name, "status") == "Completed"
	)


def _assert_portal_mutable(doc):
	if _completed_import_file(doc):
		frappe.throw(
			_("This Vehicle Import File is completed and is read-only in AN Truck Portal."),
			frappe.PermissionError,
		)


def _linked_row(doctype, name):
	if not name or not frappe.has_permission(doctype, "read", name):
		return None
	doc = frappe.get_doc(doctype, name)
	return {
		"doctype": doctype,
		"name": doc.name,
		"status": doc.get("status"),
		"docstatus": doc.docstatus,
		"date": _document_date(doc),
	}


def _linked_documents(doc):
	linked = []
	seen = set()

	def add(doctype, name):
		key = (doctype, name)
		if not name or key in seen:
			return
		seen.add(key)
		if row := _linked_row(doctype, name):
			linked.append(row)

	if doc.doctype == "Quotation":
		for name in frappe.get_all(
			"Sales Order Item",
			filters={"prevdoc_docname": doc.name, "docstatus": ["<", 2]},
			pluck="parent",
		):
			add("Sales Order", name)
	elif doc.doctype == "Sales Order":
		for row in doc.items:
			add("Quotation", row.get("prevdoc_docname"))
		for name in frappe.get_all(
			"Sales Invoice Item",
			filters={"sales_order": doc.name, "docstatus": ["<", 2]},
			pluck="parent",
		):
			add("Sales Invoice", name)
	else:
		for row in doc.items:
			add("Sales Order", row.get("sales_order"))
		for name in frappe.get_all(
			"Payment Entry Reference",
			filters={
				"reference_doctype": "Sales Invoice",
				"reference_name": doc.name,
				"docstatus": ["<", 2],
			},
			pluck="parent",
		):
			add("Payment Entry", name)
	return linked


def _encode_delivery_acknowledgment(data):
	encoded = base64.urlsafe_b64encode(
		json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
	).decode("ascii")
	return f"<!-- {DELIVERY_ACKNOWLEDGMENT_MARKER}{encoded} -->"


def _decode_delivery_acknowledgment(instructions):
	text = instructions or ""
	start = text.rfind(DELIVERY_ACKNOWLEDGMENT_MARKER)
	if start < 0:
		return None
	start += len(DELIVERY_ACKNOWLEDGMENT_MARKER)
	end = text.find(" -->", start)
	if end < 0:
		return None
	try:
		return json.loads(base64.urlsafe_b64decode(text[start:end]).decode("utf-8"))
	except (ValueError, TypeError, binascii.Error, json.JSONDecodeError):
		return None


def _submitted_vehicle_delivery(vehicle_name):
	"""Return the submitted stock document for a vehicle, independent of its entry point."""
	for delivery_note in frappe.get_all(
		"Delivery Note Item",
		filters={"custom_vehicle_master": vehicle_name, "docstatus": 1},
		pluck="parent",
	):
		if frappe.db.get_value("Delivery Note", delivery_note, "docstatus") == 1:
			return "Delivery Note", delivery_note

	# An update-stock invoice is already the stock delivery. Never create a
	# second Delivery Note for the same vehicle from its linked Sales Order.
	for sales_invoice in frappe.get_all(
		"Sales Invoice Item",
		filters={"custom_vehicle_master": vehicle_name, "docstatus": 1},
		pluck="parent",
	):
		if frappe.db.get_value("Sales Invoice", sales_invoice, "update_stock"):
			return "Sales Invoice", sales_invoice
	return None, None


def _sales_document_vehicles(doc):
	vehicles = []
	seen = set()
	for item in doc.items:
		vehicle_name = item.get("custom_vehicle_master")
		if not vehicle_name or vehicle_name in seen:
			continue
		seen.add(vehicle_name)
		if not frappe.has_permission("Vehicle Master", "read", vehicle_name):
			continue
		vehicle = frappe.db.get_value(
			"Vehicle Master",
			vehicle_name,
			[
				"name",
				"vin",
				"chassis_number",
				"plate_number",
				"item_name",
				"brand",
				"model",
				"vehicle_type",
				"vehicle_status",
				"vehicle_import_file",
				"sales_order",
				"delivery_note",
			],
			as_dict=True,
		)
		if not vehicle:
			continue
		delivery_doctype, delivery_document = _submitted_vehicle_delivery(vehicle.name)
		delivery_note = delivery_document if delivery_doctype == "Delivery Note" else None
		acknowledgment = None
		if delivery_note:
			instructions = frappe.db.get_value("Delivery Note", delivery_note, "instructions")
			acknowledgment = _decode_delivery_acknowledgment(instructions)
		elif vehicle.delivery_note and frappe.db.get_value(
			"Delivery Note", vehicle.delivery_note, "docstatus"
		) == 1:
			delivery_note = vehicle.delivery_note
			delivery_doctype, delivery_document = "Delivery Note", delivery_note
			instructions = frappe.db.get_value("Delivery Note", delivery_note, "instructions")
			acknowledgment = _decode_delivery_acknowledgment(instructions)
		sales_order = item.get("sales_order") or vehicle.sales_order
		if doc.doctype == "Sales Order":
			sales_order = doc.name
		if not sales_order and item.get("so_detail"):
			sales_order = frappe.db.get_value("Sales Order Item", item.so_detail, "parent")
		delivered = bool(
			delivery_document or cstr(vehicle.vehicle_status).lower() == "delivered"
		)
		vehicles.append(
			{
				"name": vehicle.name,
				"vin": vehicle.vin,
				"chassis_number": vehicle.chassis_number or vehicle.vin,
				"plate_number": vehicle.plate_number,
				"item_name": vehicle.item_name or item.item_name,
				"brand": vehicle.brand,
				"model": vehicle.model,
				"vehicle_type": vehicle.vehicle_type,
				"vehicle_status": vehicle.vehicle_status,
				"vehicle_import_file": vehicle.vehicle_import_file,
				"sales_order": sales_order,
				"delivery_source_type": doc.doctype,
				"delivery_source": doc.name,
				"sales_invoice_item": item.name if doc.doctype == "Sales Invoice" else None,
				"description": item.description or vehicle.item_name or item.item_name,
				"delivery_note": delivery_note,
				"delivery_document_type": delivery_doctype,
				"delivery_document": delivery_document,
				"delivered": delivered,
				"acknowledgment_available": bool(acknowledgment),
			}
		)
	return vehicles


def _delivery_letter_head(delivery_note):
	company = frappe.db.get_value(
		"Company",
		delivery_note.company,
		["name", "company_name", "company_logo", "tax_id", "default_letter_head"],
		as_dict=True,
	) or frappe._dict()
	letter_head_name = delivery_note.get("letter_head") or company.default_letter_head
	if not letter_head_name:
		letter_head_name = frappe.db.get_value(
			"Letter Head", {"is_default": 1, "disabled": 0}, "name"
		)
	letter_head = frappe._dict()
	if letter_head_name:
		letter_head = frappe.db.get_value(
			"Letter Head",
			letter_head_name,
			[
				"name",
				"source",
				"content",
				"image",
				"image_height",
				"image_width",
				"align",
				"footer_source",
				"footer",
				"footer_image",
				"footer_image_height",
				"footer_image_width",
				"footer_align",
			],
			as_dict=True,
		) or frappe._dict()
	return {"company": company, "letter_head": letter_head}


def _draft_for_source(doctype, source):
	if doctype == "Sales Order":
		return frappe.db.get_value(
			"Sales Order Item", {"prevdoc_docname": source, "docstatus": 0}, "parent"
		)
	if doctype == "Sales Invoice":
		return frappe.db.get_value(
			"Sales Invoice Item", {"sales_order": source, "docstatus": 0}, "parent"
		)
	return None


def _mapped_document(doctype, source):
	if doctype == "Sales Order":
		from erpnext.selling.doctype.quotation.quotation import make_sales_order

		doc = make_sales_order(source)
	elif doctype == "Sales Invoice":
		from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

		doc = make_sales_invoice(source)
	else:
		frappe.throw(_("Unsupported resource"), frappe.ValidationError)
	if not doc.items:
		frappe.throw(_("No remaining items are available for this document."))
	return doc


def _form_item(row, source_field=None):
	return {
		"source_item": row.get(source_field) if source_field else None,
		"item_code": row.item_code,
		"item_name": row.item_name,
		"description": row.description,
		"qty": row.qty,
		"max_qty": row.qty,
		"uom": row.uom,
		"rate": row.rate,
		"amount": row.amount,
		"warehouse": row.get("warehouse"),
		"vehicle_master": row.get("custom_vehicle_master"),
		"vin": row.get("custom_vin"),
		"vehicle_import_file": row.get("custom_vehicle_import_file"),
	}


def _sales_vehicle_options(doctype, company, source=None):
	allowed_order = source if doctype == "Sales Invoice" else None
	statuses = ["Received", "Available"] + (["Reserved"] if allowed_order else [])
	vehicles = frappe.get_list(
		"Vehicle Master",
		filters={"company": company, "disabled": 0, "vehicle_status": ["in", statuses]},
		fields=[
			"name", "vin", "chassis_number", "item_code", "item_name", "brand", "model",
			"color", "warehouse", "vehicle_status", "vehicle_import_file", "sales_order",
			"selling_rate", "final_valuation_rate",
		],
		order_by="vin asc",
		limit=500,
	)
	if not vehicles:
		return []
	names = [row.name for row in vehicles]
	active_orders = {}
	for row in frappe.get_all(
		"Sales Order Item",
		filters={"custom_vehicle_master": ["in", names], "docstatus": 1},
		fields=["custom_vehicle_master", "parent"],
	):
		active_orders.setdefault(row.custom_vehicle_master, set()).add(row.parent)
	sold = set(
		frappe.get_all(
			"Sales Invoice Item",
			filters={"custom_vehicle_master": ["in", names], "docstatus": 1},
			pluck="custom_vehicle_master",
		)
	)
	delivered = set(
		frappe.get_all(
			"Delivery Note Item",
			filters={"custom_vehicle_master": ["in", names], "docstatus": 1},
			pluck="custom_vehicle_master",
		)
	)
	result = []
	for vehicle in vehicles:
		orders = active_orders.get(vehicle.name, set())
		if vehicle.name in sold or vehicle.name in delivered:
			continue
		if orders and orders != {allowed_order}:
			continue
		if vehicle.vehicle_status == "Reserved" and (
			not allowed_order or vehicle.sales_order != allowed_order
		):
			continue
		result.append(
			{
				**vehicle,
				"description": " / ".join(
					str(value) for value in (vehicle.item_name, vehicle.brand, vehicle.model) if value
				),
				"rate": flt(vehicle.selling_rate) or flt(vehicle.final_valuation_rate),
			}
		)
	return result


def _sales_form_options(company, doctype, source=None):
	if not company:
		frappe.throw(_("Company is required."))
	frappe.get_doc("Company", company).check_permission("read")
	return {
		"company": company,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"customers": frappe.get_list(
			"Customer",
			filters={"disabled": 0},
			fields=["name", "customer_name", "default_currency"],
			order_by="customer_name asc",
			limit=500,
		),
		"item_options": frappe.get_list(
			"Item",
			filters={"disabled": 0, "is_sales_item": 1},
			fields=["name", "item_name", "stock_uom", "standard_rate"],
			order_by="item_name asc",
			limit=500,
		),
		"vehicle_options": _sales_vehicle_options(doctype, company, source),
	}


@frappe.whitelist(methods=["GET"])
def get_sales_form(doctype, source=None, company=None):
	require_access()
	_require_sales_doctype(doctype)
	if not frappe.has_permission(doctype, "create"):
		frappe.throw(_("Not permitted to create {0}.").format(_(doctype)), frappe.PermissionError)
	if doctype == "Quotation" or not source:
		options = _sales_form_options(company, doctype, source)
		return {
			"doctype": doctype,
			**options,
			"transaction_date": nowdate(),
			"delivery_date": nowdate(),
			"posting_date": nowdate(),
			"items": [],
		}
	source_doctype = "Quotation" if doctype == "Sales Order" else "Sales Order"
	source_doc = frappe.get_doc(source_doctype, source)
	source_doc.check_permission("read")
	_assert_portal_mutable(source_doc)
	if source_doc.docstatus != 1:
		frappe.throw(_("{0} {1} must be submitted.").format(_(source_doctype), source))
	if draft := _draft_for_source(doctype, source):
		frappe.throw(_("Draft {0} {1} already exists for this source.").format(_(doctype), draft))
	doc = _mapped_document(doctype, source)
	options = _sales_form_options(doc.company, doctype, source)
	source_field = "quotation_item" if doctype == "Sales Order" else "so_detail"
	return {
		"doctype": doctype,
		"source_doctype": source_doctype,
		"source": source,
		"customer": doc.customer,
		"customer_name": doc.customer_name,
		"company": doc.company,
		"currency": doc.currency,
		"transaction_date": doc.get("transaction_date") or nowdate(),
		"delivery_date": doc.get("delivery_date") or nowdate(),
		"posting_date": doc.get("posting_date") or nowdate(),
		"due_date": doc.get("due_date"),
		"items": [_form_item(row, source_field) for row in doc.items],
		"customers": options["customers"],
		"item_options": options["item_options"],
		"vehicle_options": options["vehicle_options"],
	}


def _prepare_sales_rows(doctype, company, rows, source=None):
	prepared = []
	seen = set()
	allowed_order = source if doctype == "Sales Invoice" else None
	for value in rows or []:
		row = frappe._dict(value)
		vehicle_name = cstr(row.get("vehicle_master") or row.get("custom_vehicle_master")).strip()
		if not vehicle_name:
			prepared.append(row)
			continue
		if vehicle_name in seen:
			frappe.throw(_("Vehicle {0} is selected more than once.").format(vehicle_name))
		seen.add(vehicle_name)
		if flt(row.get("qty")) != 1:
			frappe.throw(_("Quantity must be 1 for a VIN-linked vehicle row."))
		vehicle = frappe.get_doc("Vehicle Master", vehicle_name)
		vehicle.check_permission("read")
		if vehicle.disabled or vehicle.company != company:
			frappe.throw(_("Vehicle {0} is not available for this company.").format(vehicle.vin))
		active_orders = set(
			frappe.get_all(
				"Sales Order Item",
				filters={"custom_vehicle_master": vehicle.name, "docstatus": 1},
				pluck="parent",
			)
		)
		if active_orders and active_orders != {allowed_order}:
			frappe.throw(
				_("Vehicle {0} is already reserved by another Sales Order.").format(vehicle.vin)
			)
		if frappe.db.exists(
			"Sales Invoice Item", {"custom_vehicle_master": vehicle.name, "docstatus": 1}
		) or frappe.db.exists(
			"Delivery Note Item", {"custom_vehicle_master": vehicle.name, "docstatus": 1}
		):
			frappe.throw(_("Vehicle {0} has already been sold or delivered.").format(vehicle.vin))
		allowed_statuses = {"Received", "Available"}
		if allowed_order and vehicle.sales_order == allowed_order:
			allowed_statuses.add("Reserved")
		if vehicle.vehicle_status not in allowed_statuses:
			frappe.throw(
				_("Vehicle {0} is not available for sale.").format(vehicle.vin)
			)
		row.vehicle_master = vehicle.name
		row.vin = vehicle.vin
		row.vehicle_import_file = vehicle.vehicle_import_file
		row.item_code = vehicle.item_code
		row.item_name = vehicle.item_name
		row.description = row.get("description") or " / ".join(
			str(value) for value in (vehicle.item_name, vehicle.brand, vehicle.model) if value
		)
		row.warehouse = row.get("warehouse") or vehicle.warehouse
		if row.get("rate") in (None, ""):
			row.rate = flt(vehicle.selling_rate) or flt(vehicle.final_valuation_rate)
		prepared.append(row)
	return prepared


def _item_values(doc, row):
	values = {
		"item_code": row.item_code,
		"qty": flt(row.qty),
		"rate": flt(row.rate),
		"warehouse": row.get("warehouse"),
		"description": row.get("description"),
		"custom_vehicle_master": row.get("vehicle_master"),
		"custom_vin": row.get("vin"),
		"custom_vehicle_import_file": row.get("vehicle_import_file"),
	}
	if doc.doctype == "Sales Order":
		values["delivery_date"] = doc.get("delivery_date")
	return values


def _apply_items(doc, rows, source_field=None):
	rows = [frappe._dict(row) for row in rows or [] if flt(row.get("qty")) > 0]
	if not rows:
		frappe.throw(_("Select at least one item."))
	import_files = {row.get("vehicle_import_file") for row in rows if row.get("vehicle_import_file")}
	if len(import_files) == 1:
		doc.set(CUSTOM_FIELD, next(iter(import_files)))
	if not source_field:
		doc.set("items", [])
		for row in rows:
			doc.append("items", _item_values(doc, row))
		return
	selected = {row.source_item: row for row in rows if row.source_item}
	for item in list(doc.items):
		choice = selected.get(item.get(source_field))
		if not choice:
			doc.remove(item)
			continue
		if flt(choice.qty) > flt(item.qty):
			frappe.throw(_("Quantity cannot exceed the remaining source quantity."))
		if choice.get("vehicle_master") and choice.item_code != item.item_code:
			frappe.throw(_("Selected VIN does not match the source item."))
		item.qty = flt(choice.qty)
		item.rate = flt(choice.rate)
		item.warehouse = choice.get("warehouse") or item.warehouse
		item.description = choice.get("description") or item.description
		item.custom_vehicle_master = choice.get("vehicle_master")
		item.custom_vin = choice.get("vin")
		item.custom_vehicle_import_file = choice.get("vehicle_import_file")
	for row in rows:
		if row.source_item:
			continue
		frappe.get_doc("Item", row.item_code).check_permission("read")
		doc.append("items", _item_values(doc, row))
	if not doc.items:
		frappe.throw(_("Select at least one item."))


@frappe.whitelist(methods=["POST"])
def create_sales_document(doctype, data=None, source=None, submit_now=0, idempotency_key=None):
	require_access()
	_require_sales_doctype(doctype)
	if not frappe.has_permission(doctype, "create"):
		frappe.throw(_("Not permitted to create {0}.").format(_(doctype)), frappe.PermissionError)
	data = frappe.parse_json(data) if isinstance(data, str) else frappe._dict(data or {})
	if not idempotency_key:
		frappe.throw(_("Unable to safely process this document. Please reopen the form and try again."))
	cache_key = f"an_truck_portal:sales:{doctype}:{source or data.get('customer')}:{idempotency_key}"
	if existing := frappe.cache().get_value(cache_key):
		return existing

	if doctype == "Quotation" or not source:
		if not data.get("customer"):
			frappe.throw(_("Customer is required."))
		if not data.get("company"):
			frappe.throw(_("Company is required."))
		customer = frappe.get_doc("Customer", data.get("customer"))
		customer.check_permission("read")
		company = frappe.get_doc("Company", data.get("company"))
		company.check_permission("read")
		doc = frappe.new_doc(doctype)
		if doctype == "Quotation":
			doc.quotation_to = "Customer"
			doc.party_name = data.get("customer")
		else:
			doc.customer = data.get("customer")
		doc.company = data.get("company")
		doc.currency = data.get("currency") or customer.default_currency or company.default_currency
		if doctype in {"Quotation", "Sales Order"}:
			doc.transaction_date = data.get("transaction_date") or nowdate()
		if doctype == "Quotation":
			doc.valid_till = data.get("valid_till")
		elif doctype == "Sales Order":
			doc.delivery_date = data.get("delivery_date") or nowdate()
		else:
			doc.posting_date = data.get("posting_date") or nowdate()
			doc.due_date = data.get("due_date")
		rows = _prepare_sales_rows(doctype, doc.company, data.get("items"), source)
		for row in rows:
			if row.get("item_code"):
				frappe.get_doc("Item", row.item_code).check_permission("read")
		_apply_items(doc, rows)
	else:
		source_doctype = "Quotation" if doctype == "Sales Order" else "Sales Order"
		source_doc = frappe.get_doc(source_doctype, source, for_update=True)
		source_doc.check_permission("read")
		if existing := frappe.cache().get_value(cache_key):
			return existing
		_assert_portal_mutable(source_doc)
		if source_doc.docstatus != 1:
			frappe.throw(_("{0} {1} must be submitted.").format(_(source_doctype), source))
		if draft := _draft_for_source(doctype, source):
			frappe.throw(_("Draft {0} {1} already exists for this source.").format(_(doctype), draft))
		doc = _mapped_document(doctype, source)
		source_field = "quotation_item" if doctype == "Sales Order" else "so_detail"
		rows = _prepare_sales_rows(doctype, doc.company, data.get("items"), source)
		_apply_items(doc, rows, source_field)
		if doctype == "Sales Order":
			doc.transaction_date = data.get("transaction_date") or nowdate()
			doc.delivery_date = data.get("delivery_date") or nowdate()
		else:
			doc.posting_date = data.get("posting_date") or nowdate()
			doc.due_date = data.get("due_date")
	if data.get("remarks"):
		doc.remarks = data.remarks
	doc.run_method("set_missing_values")
	doc.run_method("calculate_taxes_and_totals")
	doc.insert()
	if cint(submit_now):
		doc.submit()
	result = {"doctype": doc.doctype, "name": doc.name, "docstatus": doc.docstatus, "status": doc.status}
	frappe.cache().set_value(cache_key, result, expires_in_sec=60 * 60)
	return result


@frappe.whitelist(methods=["POST"])
def upload_sales_attachment(doctype, document):
	require_access()
	_require_sales_doctype(doctype)
	if frappe.form_dict.doctype != doctype or frappe.form_dict.docname != document:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	doc = frappe.get_doc(doctype, document)
	doc.check_permission("write")
	_assert_portal_mutable(doc)
	return upload_file()


@frappe.whitelist(methods=["GET"])
def get_sales_document(doctype, document):
	require_access()
	_require_sales_doctype(doctype)
	doc = frappe.get_doc(doctype, document)
	doc.check_permission("read")
	party = doc.get("party_name") if doctype == "Quotation" else doc.get("customer")
	party_name = doc.get("customer_name") or party
	items = []
	for row in doc.items:
		items.append(
			{
				"name": row.name,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"description": row.description,
				"qty": row.qty,
				"uom": row.uom,
				"rate": row.rate,
				"amount": row.amount,
				"warehouse": row.get("warehouse"),
				"quotation": row.get("prevdoc_docname"),
				"sales_order": row.get("sales_order"),
			}
		)
	next_doctype = "Sales Order" if doctype == "Quotation" else "Sales Invoice" if doctype == "Sales Order" else None
	can_create_next = False
	if (
		next_doctype
		and doc.docstatus == 1
		and not _completed_import_file(doc)
		and frappe.has_permission(next_doctype, "create")
	):
		try:
			can_create_next = not _draft_for_source(next_doctype, doc.name) and bool(
				_mapped_document(next_doctype, doc.name).items
			)
		except Exception:
			can_create_next = False
	vehicle_deliveries = (
		_sales_document_vehicles(doc)
		if doctype in {"Sales Order", "Sales Invoice"}
		else []
	)
	can_deliver_vehicle = False
	delivery_block_reason = None
	if doctype in {"Sales Order", "Sales Invoice"}:
		if doc.docstatus != 1:
			delivery_block_reason = _("Sales document must be submitted before delivering a vehicle.")
		elif not vehicle_deliveries:
			delivery_block_reason = _("This sales document is not linked to any vehicles.")
		elif doctype == "Sales Invoice" and doc.get("update_stock"):
			delivery_block_reason = _(
				"This Sales Invoice already includes the stock delivery movement."
			)
		elif not any(not row["delivered"] for row in vehicle_deliveries):
			delivery_block_reason = _(
				"All vehicles linked to this sales document have already been delivered."
			)
		elif _completed_import_file(doc):
			delivery_block_reason = _(
				"This Vehicle Import File is completed and is read-only in AN Truck Portal."
			)
		elif not frappe.has_permission("Delivery Note", "create") or not frappe.has_permission(
			"Delivery Note", "submit"
		):
			delivery_block_reason = _("Not permitted to create and submit Delivery Note.")
		else:
			can_deliver_vehicle = True
	warranty_context = None
	if doctype == "Sales Invoice" and frappe.has_permission("Vehicle Warranty", "read"):
		from an_truck.warranty.workflow import get_invoice_warranty_context
		warranty_context = get_invoice_warranty_context(doc.name)
	return {
		"document": {
			"doctype": doctype,
			"name": doc.name,
			"customer": party,
			"customer_name": party_name,
			"company": doc.get("company"),
			"transaction_date": doc.get("transaction_date"),
			"posting_date": doc.get("posting_date"),
			"valid_till": doc.get("valid_till"),
			"delivery_date": doc.get("delivery_date"),
			"due_date": doc.get("due_date"),
			"currency": doc.get("currency"),
			"status": doc.get("status"),
			"docstatus": doc.docstatus,
			"total_qty": doc.get("total_qty"),
			"net_total": doc.get("net_total"),
			"total_taxes_and_charges": doc.get("total_taxes_and_charges"),
			"grand_total": doc.get("grand_total"),
			"rounded_total": doc.get("rounded_total"),
			"outstanding_amount": doc.get("outstanding_amount"),
			"paid_amount": doc.get("paid_amount"),
			"remarks": doc.get("remarks"),
		},
		"items": items,
		"attachments": _files(doctype, doc.name),
		"linked_documents": _linked_documents(doc),
		"next_doctype": next_doctype,
		"can_create_next": can_create_next,
		"can_record_payment": bool(
			doctype == "Sales Invoice"
			and doc.docstatus == 1
			and flt(doc.outstanding_amount) > 0
			and not _completed_import_file(doc)
			and frappe.has_permission("Payment Entry", "create")
		),
		"can_submit": bool(doc.docstatus == 0 and doc.has_permission("submit")),
		"vehicle_deliveries": vehicle_deliveries,
		"can_deliver_vehicle": can_deliver_vehicle,
		"delivery_block_reason": delivery_block_reason,
		"warranty_context": warranty_context,
		"desk_url": f"/app/{frappe.scrub(doctype).replace('_', '-')}/{quote(doc.name)}",
	}


@frappe.whitelist(methods=["GET"])
def get_sales_print_options(doctype, document):
	require_access()
	_require_sales_doctype(doctype)
	doc = frappe.get_doc(doctype, document)
	from frappe.www.printview import validate_print

	validate_print(doc)
	formats = ["Standard"]
	for row in frappe.get_all(
		"Print Format",
		filters={"doc_type": doctype, "docstatus": ["<", 2], "disabled": 0},
		fields=["name", "print_format_type", "raw_printing"],
		order_by="name asc",
	):
		if row.print_format_type == "JS" or row.raw_printing:
			continue
		if row.name not in formats:
			formats.append(row.name)
	default_format = doc.get("pos_print_format") if doc.get("is_pos") else None
	default_format = default_format or frappe.get_meta(doctype).default_print_format or "Standard"
	if default_format not in formats:
		default_format = "Standard"
	return {
		"doctype": doctype,
		"document": doc.name,
		"default_format": default_format,
		"formats": formats,
	}


def _vehicle_delivery_source(source_doctype=None, source_name=None, sales_invoice=None, sales_order=None):
	if sales_invoice:
		source_doctype, source_name = "Sales Invoice", sales_invoice
	elif sales_order:
		source_doctype, source_name = "Sales Order", sales_order
	if source_doctype not in {"Sales Order", "Sales Invoice"} or not source_name:
		frappe.throw(_("Select a valid sales document."))
	return source_doctype, source_name


@frappe.whitelist(methods=["GET"])
def get_vehicle_delivery_form(
	source_doctype=None, source_name=None, sales_invoice=None, sales_order=None
):
	require_access()
	source_doctype, source_name = _vehicle_delivery_source(
		source_doctype, source_name, sales_invoice, sales_order
	)
	doc = frappe.get_doc(source_doctype, source_name)
	doc.check_permission("read")
	_assert_portal_mutable(doc)
	if doc.docstatus != 1:
		frappe.throw(_("Sales document must be submitted before delivering a vehicle."))
	if source_doctype == "Sales Invoice" and doc.get("update_stock"):
		frappe.throw(_("This Sales Invoice already includes the stock delivery movement."))
	if not frappe.has_permission("Delivery Note", "create") or not frappe.has_permission(
		"Delivery Note", "submit"
	):
		frappe.throw(_("Not permitted to create and submit Delivery Note."), frappe.PermissionError)
	vehicles = _sales_document_vehicles(doc)
	if not vehicles:
		frappe.throw(_("This sales document is not linked to any vehicles."))
	available = [
		row for row in vehicles if not row["delivered"] and row["delivery_source"]
	]
	if not available:
		frappe.throw(_("All vehicles linked to this sales document have already been delivered."))
	return {
		"source_doctype": source_doctype,
		"source_name": doc.name,
		"sales_invoice": doc.name if source_doctype == "Sales Invoice" else None,
		"customer": doc.customer,
		"customer_name": doc.customer_name or doc.customer,
		"company": doc.company,
		"delivery_date": nowdate(),
		"delivery_employee": frappe.db.get_value("User", frappe.session.user, "full_name")
		or frappe.session.user,
		"vehicles": available,
	}


@frappe.whitelist(methods=["POST"])
def confirm_vehicle_delivery(
	source_doctype=None,
	source_name=None,
	sales_invoice=None,
	sales_order=None,
	data=None,
	idempotency_key=None,
):
	from an_truck import transactions

	require_access()
	data = frappe.parse_json(data) if isinstance(data, str) else frappe._dict(data or {})
	if not idempotency_key:
		frappe.throw(_("Unable to safely confirm delivery. Please reopen the form and try again."))
	if not frappe.has_permission("Delivery Note", "create") or not frappe.has_permission(
		"Delivery Note", "submit"
	):
		frappe.throw(_("Not permitted to create and submit Delivery Note."), frappe.PermissionError)

	source_doctype, source_name = _vehicle_delivery_source(
		source_doctype, source_name, sales_invoice, sales_order
	)
	doc = frappe.get_doc(source_doctype, source_name, for_update=True)
	doc.check_permission("read")
	_assert_portal_mutable(doc)
	if doc.docstatus != 1:
		frappe.throw(_("Sales document must be submitted before delivering a vehicle."))
	if source_doctype == "Sales Invoice" and doc.get("update_stock"):
		frappe.throw(_("This Sales Invoice already includes the stock delivery movement."))

	vehicle_name = cstr(data.get("vehicle_master")).strip()
	source_item = next(
		(row for row in doc.items if row.get("custom_vehicle_master") == vehicle_name), None
	)
	if not vehicle_name or not source_item:
		frappe.throw(_("Select a vehicle linked to this sales document."))
	vehicle = frappe.get_doc("Vehicle Master", vehicle_name, for_update=True)
	vehicle.check_permission("read")
	delivery_doctype, delivery_document = _submitted_vehicle_delivery(vehicle.name)
	if delivery_document or cstr(vehicle.vehicle_status).lower() == "delivered":
		if delivery_doctype == "Delivery Note":
			existing = frappe.get_doc("Delivery Note", delivery_document)
			acknowledgment = _decode_delivery_acknowledgment(existing.instructions)
			if acknowledgment and acknowledgment.get("vehicle_master") == vehicle.name:
				return {
					"doctype": "Delivery Note",
					"name": existing.name,
					"vehicle_master": vehicle.name,
					"already_confirmed": True,
				}
		frappe.throw(_("Vehicle {0} has already been delivered.").format(vehicle.vin))

	import_file = doc.get(CUSTOM_FIELD) or vehicle.vehicle_import_file
	if not import_file:
		frappe.throw(_("The selected vehicle is not linked to a Vehicle Import File."))
	delivery_date = getdate(data.get("delivery_date") or nowdate())
	accessories = {
		fieldname: bool(cint((data.get("accessories") or {}).get(fieldname)))
		for fieldname in DELIVERY_ACCESSORIES
	}
	payload = {
		"version": 1,
		"source_doctype": source_doctype,
		"source_name": doc.name,
		"sales_invoice": doc.name if source_doctype == "Sales Invoice" else None,
		"customer": doc.customer,
		"customer_name": doc.customer_name or doc.customer,
		"delivery_date": str(delivery_date),
		"vehicle_master": vehicle.name,
		"vehicle_type": vehicle.vehicle_type,
		"model": vehicle.model,
		"vin": vehicle.vin,
		"chassis_number": vehicle.chassis_number or vehicle.vin,
		"plate_number": vehicle.plate_number,
		"vehicle_description": source_item.description or vehicle.item_name,
		"accessories": accessories,
		"other_description": cstr(data.get("other_description")).strip()
		if accessories["other"]
		else "",
		"notes": cstr(data.get("notes")).strip(),
		"customer_representative_name": cstr(
			data.get("customer_representative_name")
		).strip(),
		"representative_id": cstr(data.get("representative_id")).strip(),
		"delivery_employee_name": cstr(data.get("delivery_employee_name")).strip()
		or frappe.db.get_value("User", frappe.session.user, "full_name")
		or frappe.session.user,
		"confirmed_by": frappe.session.user,
		"confirmed_at": str(now_datetime()),
	}
	result = transactions.create_delivery_note(
		import_file,
		{
			"source_type": source_doctype,
			"source_name": source_name,
			"posting_date": str(delivery_date),
			"vehicles": [{"vehicle_master": vehicle.name}],
			"delivery_acknowledgment": _encode_delivery_acknowledgment(payload),
		},
		submit_now=1,
		idempotency_key=idempotency_key,
	)
	result.update({"vehicle_master": vehicle.name, "already_confirmed": False})
	return result


@frappe.whitelist(methods=["GET"])
def get_vehicle_delivery_acknowledgment(delivery_note):
	require_access()
	doc = frappe.get_doc("Delivery Note", delivery_note)
	doc.check_permission("read")
	if doc.docstatus != 1:
		frappe.throw(_("Vehicle Delivery Note must be submitted."))
	acknowledgment = _decode_delivery_acknowledgment(doc.instructions)
	if not acknowledgment:
		frappe.throw(_("Vehicle delivery acknowledgment was not found."), frappe.DoesNotExistError)
	if acknowledgment.get("sales_invoice"):
		frappe.get_doc("Sales Invoice", acknowledgment["sales_invoice"]).check_permission("read")
	elif acknowledgment.get("source_doctype") and acknowledgment.get("source_name"):
		frappe.get_doc(
			acknowledgment["source_doctype"], acknowledgment["source_name"]
		).check_permission("read")
	if acknowledgment.get("vehicle_master"):
		frappe.get_doc("Vehicle Master", acknowledgment["vehicle_master"]).check_permission("read")
	header = _delivery_letter_head(doc)
	return {
		"delivery_note": doc.name,
		"posting_date": doc.posting_date,
		"company": header["company"],
		"letter_head": header["letter_head"],
		"acknowledgment": acknowledgment,
	}


@frappe.whitelist(methods=["GET"])
def get_customer_payment_form(sales_invoice):
	from an_truck_portal.api.import_file import _payment_modes

	require_access()
	invoice = frappe.get_doc("Sales Invoice", sales_invoice)
	invoice.check_permission("read")
	_assert_portal_mutable(invoice)
	if not frappe.has_permission("Payment Entry", "create"):
		frappe.throw(_("Not permitted to create Payment Entry."), frappe.PermissionError)
	if invoice.docstatus != 1 or flt(invoice.outstanding_amount) <= 0:
		frappe.throw(_("This Sales Invoice has no outstanding balance."))
	modes = _payment_modes(invoice.company)
	default_mode = invoice.get("mode_of_payment")
	if default_mode not in {mode["name"] for mode in modes}:
		default_mode = modes[0]["name"] if len(modes) == 1 else ""
	return {
		"sales_invoice": invoice.name,
		"customer": invoice.customer,
		"customer_name": invoice.customer_name,
		"company": invoice.company,
		"currency": invoice.currency,
		"outstanding_amount": invoice.outstanding_amount,
		"payment_date": nowdate(),
		"reference_date": nowdate(),
		"mode_of_payment": default_mode,
		"modes_of_payment": modes,
	}


@frappe.whitelist(methods=["POST"])
def record_customer_payment(sales_invoice, data=None, idempotency_key=None):
	from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	require_access()
	data = frappe.parse_json(data) if isinstance(data, str) else frappe._dict(data or {})
	if not idempotency_key:
		frappe.throw(_("Unable to safely process this payment. Please reopen the form and try again."))
	cache_key = f"an_truck_portal:customer_payment:{sales_invoice}:{idempotency_key}"
	if existing := frappe.cache().get_value(cache_key):
		return existing
	invoice = frappe.get_doc("Sales Invoice", sales_invoice, for_update=True)
	invoice.check_permission("read")
	if existing := frappe.cache().get_value(cache_key):
		return existing
	_assert_portal_mutable(invoice)
	if invoice.docstatus != 1 or flt(invoice.outstanding_amount) <= 0:
		frappe.throw(_("This Sales Invoice has no outstanding balance."))
	amount = flt(data.get("amount"), invoice.precision("outstanding_amount"))
	if amount <= 0 or amount > flt(invoice.outstanding_amount, invoice.precision("outstanding_amount")):
		frappe.throw(_("Payment amount must be greater than zero and cannot exceed the outstanding amount."))
	mode = data.get("mode_of_payment")
	if not mode:
		frappe.throw(_("Mode of Payment is required."))
	if not frappe.db.get_value("Mode of Payment", mode, "enabled"):
		frappe.throw(_("Mode of Payment {0} is disabled.").format(mode))
	bank = get_default_bank_cash_account(invoice.company, mode_of_payment=mode, fetch_balance=False)
	if not bank:
		frappe.throw(_("No account is configured for Mode of Payment {0}.").format(mode))
	doc = get_payment_entry(
		"Sales Invoice",
		invoice.name,
		party_amount=amount,
		bank_account=bank.account,
		reference_date=data.get("reference_date") or data.get("payment_date") or nowdate(),
	)
	doc.mode_of_payment = mode
	doc.posting_date = data.get("payment_date") or nowdate()
	doc.reference_no = data.get("reference_number")
	doc.reference_date = data.get("reference_date") or doc.posting_date
	if data.get("notes"):
		doc.custom_remarks = 1
		doc.remarks = data.notes
	doc.set_exchange_rate()
	doc.set_amounts()
	doc.insert()
	doc.submit()
	result = {"doctype": doc.doctype, "name": doc.name, "docstatus": doc.docstatus, "status": doc.status}
	frappe.cache().set_value(cache_key, result, expires_in_sec=60 * 60)
	return result


@frappe.whitelist(methods=["POST"])
def upload_customer_payment_attachment(payment_entry, sales_invoice):
	require_access()
	if frappe.form_dict.doctype != "Payment Entry" or frappe.form_dict.docname != payment_entry:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	doc = frappe.get_doc("Payment Entry", payment_entry)
	doc.check_permission("read")
	if doc.payment_type != "Receive" or doc.party_type != "Customer":
		frappe.throw(_("This payment is not a customer payment."), frappe.PermissionError)
	if not any(
		row.reference_doctype == "Sales Invoice" and row.reference_name == sales_invoice
		for row in doc.references
	):
		frappe.throw(_("Payment Entry is not linked to this Sales Invoice."), frappe.PermissionError)
	invoice = frappe.get_doc("Sales Invoice", sales_invoice)
	invoice.check_permission("read")
	_assert_portal_mutable(invoice)
	return upload_file()


@frappe.whitelist(methods=["GET"])
def get_customer_payment(payment_entry):
	require_access()
	doc = frappe.get_doc("Payment Entry", payment_entry)
	doc.check_permission("read")
	if doc.payment_type != "Receive" or doc.party_type != "Customer":
		frappe.throw(_("This payment is not a customer payment."))
	return {
		"payment": {
			"name": doc.name,
			"customer": doc.party,
			"customer_name": doc.party_name,
			"company": doc.company,
			"posting_date": doc.posting_date,
			"payment_method": doc.mode_of_payment,
			"paid_from": doc.paid_from,
			"paid_to": doc.paid_to,
			"paid_amount": doc.paid_amount,
			"received_amount": doc.received_amount,
			"paid_from_currency": doc.paid_from_account_currency,
			"paid_to_currency": doc.paid_to_account_currency,
			"reference_no": doc.reference_no,
			"reference_date": doc.reference_date,
			"status": doc.status,
			"docstatus": doc.docstatus,
			"remarks": doc.remarks,
		},
		"references": [
			{
				"name": row.name,
				"doctype": row.reference_doctype,
				"document": row.reference_name,
				"total_amount": row.total_amount,
				"outstanding_amount": row.outstanding_amount,
				"allocated_amount": row.allocated_amount,
				"exchange_rate": row.exchange_rate,
			}
			for row in doc.references
		],
		"attachments": _files("Payment Entry", doc.name),
	}
