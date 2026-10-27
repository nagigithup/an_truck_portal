import json
from urllib.parse import quote

import frappe
from frappe import _
from frappe.handler import upload_file
from frappe.model import get_permitted_fields

from an_truck_portal.access import require_read

ALLOWED = {
	"Vehicle Import File": [
		"name",
		"import_title",
		"company",
		"supplier",
		"status",
		"country_of_origin",
		"contract_number",
		"contract_date",
		"supplier_currency",
		"total_contract_amount",
		"expected_arrival_date",
		"port_of_destination",
		"total_expected_vehicles",
		"total_received_vehicles",
		"total_remaining_vehicles",
		"modified",
	],
	"Vehicle Master": [
		"name",
		"vin",
		"chassis_number",
		"company",
		"item_code",
		"item_name",
		"vehicle_status",
		"brand",
		"model",
		"model_year",
		"color",
		"vehicle_import_file",
		"supplier",
		"purchase_receipt",
		"warehouse",
		"customer",
		"sales_order",
		"sales_invoice",
		"modified",
	],
	"Purchase Order": [
		"name",
		"company",
		"supplier",
		"transaction_date",
		"currency",
		"grand_total",
		"status",
		"docstatus",
		"modified",
	],
	"Purchase Receipt": [
		"name",
		"company",
		"supplier",
		"posting_date",
		"currency",
		"grand_total",
		"status",
		"docstatus",
		"modified",
	],
	"Purchase Invoice": [
		"name",
		"company",
		"supplier",
		"posting_date",
		"currency",
		"grand_total",
		"outstanding_amount",
		"status",
		"docstatus",
		"modified",
	],
	"Supplier": ["name", "supplier_name", "supplier_group", "country", "disabled", "modified"],
	"Customer": ["name", "customer_name", "customer_group", "territory", "disabled", "modified"],
	"Quotation": [
		"name",
		"company",
		"party_name",
		"customer_name",
		"transaction_date",
		"currency",
		"grand_total",
		"status",
		"docstatus",
		"modified",
	],
	"Sales Order": [
		"name",
		"company",
		"customer",
		"customer_name",
		"transaction_date",
		"currency",
		"grand_total",
		"status",
		"docstatus",
		"modified",
	],
	"Sales Invoice": [
		"name",
		"company",
		"customer",
		"customer_name",
		"posting_date",
		"currency",
		"grand_total",
		"outstanding_amount",
		"status",
		"docstatus",
		"modified",
	],
	"Payment Entry": [
		"name",
		"company",
		"payment_type",
		"party_type",
		"party",
		"posting_date",
		"paid_amount",
		"received_amount",
		"status",
		"docstatus",
		"modified",
	],
	"Landed Cost Voucher": [
		"name",
		"company",
		"posting_date",
		"total_taxes_and_charges",
		"docstatus",
		"modified",
	],
	"Serial No": ["name", "item_code", "warehouse", "status", "modified"],
	"Quality Inspection": [
		"name",
		"inspection_type",
		"reference_type",
		"reference_name",
		"item_code",
		"sample_size",
		"status",
		"docstatus",
		"modified",
	],
}


@frappe.whitelist()
def list_records(doctype, search=None, company=None, page=1, page_length=20, filters=None):
	if doctype not in ALLOWED:
		frappe.throw("Unsupported resource", frappe.ValidationError)
	require_read(doctype)
	meta = frappe.get_meta(doctype)
	fs = json.loads(filters) if isinstance(filters, str) and filters else (filters or {})
	if company and meta.has_field("company"):
		fs["company"] = company
	or_filters = None
	if search:
		search_fields = [
			f
			for f in ("name", "import_title", "vin", "supplier_name", "customer_name")
			if f == "name" or meta.has_field(f)
		]
		or_filters = [[doctype, f, "like", f"%{search}%"] for f in search_fields]
	rows = frappe.get_list(
		doctype,
		filters=fs,
		or_filters=or_filters,
		fields=ALLOWED[doctype],
		order_by="modified desc",
		start=(int(page) - 1) * int(page_length),
		page_length=min(int(page_length), 100),
	)
	if doctype == "Vehicle Master":
		import_files = {row.vehicle_import_file for row in rows if row.vehicle_import_file}
		statuses = (
			{
				row.name: row.status
				for row in frappe.get_all(
					"Vehicle Import File",
					filters={"name": ["in", list(import_files)]},
					fields=["name", "status"],
				)
			}
			if import_files
			else {}
		)
		warranties = {}
		if rows and frappe.has_permission("Vehicle Warranty", "read"):
			for warranty in frappe.get_list(
				"Vehicle Warranty",
				filters={"vehicle_master": ["in", [row.name for row in rows]]},
				fields=["name", "vehicle_master", "status", "warranty_expiry_date"],
				order_by="warranty_start_date desc, modified desc",
				page_length=0,
			):
				warranties.setdefault(
					warranty.vehicle_master,
					{
						"name": warranty.name,
						"status": warranty.status,
						"expiry_date": warranty.warranty_expiry_date,
					},
				)
		for row in rows:
			row["warranty"] = warranties.get(row.name)
			row["_can_edit"] = (
				frappe.has_permission("Vehicle Master", "write", row.name)
				and statuses.get(row.vehicle_import_file) != "Completed"
			)
	return {"rows": rows, "page": int(page)}


@frappe.whitelist()
def get_record(doctype, name):
	if doctype not in ALLOWED:
		frappe.throw("Unsupported resource", frappe.ValidationError)
	require_read(doctype)
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	return {
		"record": {f: doc.get(f) for f in ALLOWED[doctype]},
		"desk_url": f"/app/{frappe.scrub(doctype).replace('_', '-')}/{quote(name)}",
	}


def _vehicle_is_completed(doc):
	return bool(
		doc.vehicle_import_file
		and frappe.get_cached_value("Vehicle Import File", doc.vehicle_import_file, "status") == "Completed"
	)


def _vehicle_sections(doc):
	meta = doc.meta
	read_fields = set(get_permitted_fields("Vehicle Master", permission_type="read"))
	write_fields = set(get_permitted_fields("Vehicle Master", permission_type="write"))
	sections = []
	section = {"label": _("Vehicle Details"), "fields": []}
	for field in meta.fields:
		if field.hidden:
			continue
		if field.fieldtype in {"Section Break", "Tab Break"}:
			if section["fields"]:
				sections.append(section)
			section = {"label": _(field.label or "Vehicle Details"), "fields": []}
			continue
		if field.fieldtype in {"Column Break", "Heading", "HTML", "Button"} or (
			field.fieldname not in read_fields and field.fieldtype not in {"Table", "Table MultiSelect"}
		):
			continue
		value = doc.get(field.fieldname)
		result = {
			"fieldname": field.fieldname,
			"label": _(field.label or field.fieldname.replace("_", " ").title()),
			"fieldtype": field.fieldtype,
			"options": field.options,
			"required": bool(field.reqd),
			"read_only": bool(
				field.read_only
				or (
					field.fieldname not in write_fields
					and field.fieldtype not in {"Table", "Table MultiSelect"}
				)
			),
			"description": _(field.description) if field.description else "",
		}
		if field.fieldtype == "Select":
			result["choices"] = [
				{"value": choice, "label": _(choice)}
				for choice in (field.options or "").splitlines()
				if choice
			]
		elif field.fieldtype in {"Table", "Table MultiSelect"} and field.options:
			child_meta = frappe.get_meta(field.options)
			child_read_fields = set(
				get_permitted_fields(field.options, parenttype="Vehicle Master", permission_type="read")
			)
			child_write_fields = set(
				get_permitted_fields(field.options, parenttype="Vehicle Master", permission_type="write")
			)
			result["child_fields"] = [
				{
					"fieldname": child.fieldname,
					"label": _(child.label or child.fieldname.replace("_", " ").title()),
					"fieldtype": child.fieldtype,
					"options": child.options,
					"required": bool(child.reqd),
					"read_only": bool(child.read_only or child.fieldname not in child_write_fields),
					"choices": [
						{"value": choice, "label": _(choice)}
						for choice in (child.options or "").splitlines()
						if choice
					]
					if child.fieldtype == "Select"
					else [],
				}
				for child in child_meta.fields
				if not child.hidden
				and child.fieldname in child_read_fields
				and child.fieldtype not in {"Section Break", "Column Break", "Heading", "HTML", "Button"}
			]
			value = [
				{
					"_name": row.name,
					**{child["fieldname"]: row.get(child["fieldname"]) for child in result["child_fields"]},
				}
				for row in value or []
			]
		result["value"] = value
		section["fields"].append(result)
	if section["fields"]:
		sections.append(section)
	return sections


@frappe.whitelist(methods=["GET"])
def get_vehicle_form(vehicle_master):
	require_read("Vehicle Master")
	doc = frappe.get_doc("Vehicle Master", vehicle_master)
	doc.check_permission("read")
	completed = _vehicle_is_completed(doc)
	return {
		"name": doc.name,
		"vin": doc.vin,
		"sections": _vehicle_sections(doc),
		"can_edit": bool(doc.has_permission("write") and not completed),
		"completed_import_file": completed,
		"desk_url": f"/app/vehicle-master/{quote(doc.name)}",
	}


def _assert_vehicle_portal_write(doc):
	doc.check_permission("write")
	if _vehicle_is_completed(doc):
		frappe.throw(
			_("This Vehicle Import File is completed and is read-only in AN Truck Portal."),
			frappe.PermissionError,
		)


@frappe.whitelist(methods=["POST"])
def update_vehicle(vehicle_master, values=None):
	doc = frappe.get_doc("Vehicle Master", vehicle_master)
	_assert_vehicle_portal_write(doc)
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	target_import_file = values.get("vehicle_import_file")
	if (
		target_import_file
		and frappe.get_cached_value("Vehicle Import File", target_import_file, "status") == "Completed"
	):
		frappe.throw(
			_("This Vehicle Import File is completed and is read-only in AN Truck Portal."),
			frappe.PermissionError,
		)
	write_fields = set(get_permitted_fields("Vehicle Master", permission_type="write"))
	for field in doc.meta.fields:
		if (
			field.hidden
			or field.read_only
			or (field.fieldname not in write_fields and field.fieldtype not in {"Table", "Table MultiSelect"})
			or field.fieldname not in values
			or field.fieldtype in {"Section Break", "Column Break", "Tab Break", "Heading", "HTML", "Button"}
		):
			continue
		if field.fieldtype in {"Table", "Table MultiSelect"}:
			child_meta = frappe.get_meta(field.options)
			child_write_fields = set(
				get_permitted_fields(field.options, parenttype="Vehicle Master", permission_type="write")
			)
			rows = []
			for row in values.get(field.fieldname) or []:
				row_values = {
					child.fieldname: row.get(child.fieldname)
					for child in child_meta.fields
					if not child.hidden
					and not child.read_only
					and child.fieldname in child_write_fields
					and child.fieldname in row
				}
				if row.get("_name"):
					row_values["name"] = row.get("_name")
				rows.append(row_values)
			doc.set(field.fieldname, rows)
		else:
			doc.set(field.fieldname, values.get(field.fieldname))
	doc.save()
	return {"name": doc.name, "vin": doc.vin, "modified": doc.modified}


@frappe.whitelist(methods=["POST"])
def upload_vehicle_attachment(vehicle_master, fieldname):
	doc = frappe.get_doc("Vehicle Master", vehicle_master)
	_assert_vehicle_portal_write(doc)
	field = doc.meta.get_field(fieldname)
	write_fields = set(get_permitted_fields("Vehicle Master", permission_type="write"))
	if (
		not field
		or field.fieldtype not in {"Attach", "Attach Image"}
		or field.read_only
		or fieldname not in write_fields
	):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if frappe.form_dict.doctype != "Vehicle Master" or frappe.form_dict.docname != doc.name:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	file = upload_file()
	doc.set(fieldname, file.file_url)
	doc.save()
	return {"name": file.name, "file_name": file.file_name, "file_url": file.file_url}
