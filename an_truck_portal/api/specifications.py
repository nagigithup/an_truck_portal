"""Portal adapters for the domain-owned, permission checked specification revisions."""
import frappe
from frappe import _
from frappe.model import get_permitted_fields
from frappe.utils import cint

from an_truck_portal.access import require_access, require_read
from an_truck.an_truck.doctype.vehicle_specification_template import vehicle_specification_template as domain
from an_truck.vehicle_quotation import ASSET_FIELDS, template_photos

DOCTYPE = "Vehicle Specification Template"


@frappe.whitelist()
def template_options(search="", item_code=None):
	require_read(DOCTYPE)
	filters = {"status": "Published", "active": 1}
	if item_code:
		filters["item_code"] = ["in", ["", item_code]]
	return frappe.get_list(
		DOCTYPE, filters=filters,
		or_filters=[[DOCTYPE, key, "like", f"%{str(search or '').strip()[:100]}%"] for key in ("name", "template_name", "brand", "model")],
		pluck="name", order_by="modified desc", page_length=30,
	)


@frappe.whitelist()
def list_templates(search="", page=1, page_length=20, published_only=0, item_code=None):
	require_read(DOCTYPE)
	filters = {"active": 1, "status": "Published"} if cint(published_only) else {}
	if item_code:
		frappe.get_doc("Item", item_code).check_permission("read")
		# An unassociated template is also usable for this item.
		filters["item_code"] = ["in", ["", item_code]]
	or_filters = [[DOCTYPE, field, "like", f"%{str(search).strip()[:100]}%"] for field in ("name", "template_name", "brand", "model", "item_code")] if search else None
	page, page_length = max(cint(page), 1), min(max(cint(page_length), 1), 100)
	rows = frappe.get_list(DOCTYPE, filters=filters, or_filters=or_filters,
		fields=["name", "template_name", "revision", "status", "active", "item_code", "brand", "model"],
		order_by="modified desc", start=(page - 1) * page_length, page_length=page_length + 1)
	return {"rows": rows[:page_length], "has_more": len(rows) > page_length,
		"can_create": bool(frappe.has_permission(DOCTYPE, "create"))}


@frappe.whitelist()
def get_template(name=None, company=None):
	require_read(DOCTYPE)
	doc = domain._template(name) if name else frappe.new_doc(DOCTYPE)
	if not name:
		doc.check_permission("create")
	read = set(get_permitted_fields(DOCTYPE, permission_type="read"))
	write = set(get_permitted_fields(DOCTYPE, permission_type="write"))
	sections, section = [], None
	for field in doc.meta.fields:
		if field.fieldtype == "Section Break":
			section = {"label": _(field.label), "fields": []}
			sections.append(section)
			continue
		if not section or field.hidden or field.fieldtype == "Column Break" or (field.fieldname not in read and field.fieldtype != "Table"):
			continue
		section["fields"].append({
			"fieldname": field.fieldname, "label": _(field.label), "fieldtype": field.fieldtype,
			"options": field.options, "required": bool(field.reqd),
			"read_only": bool(field.read_only or field.fieldname not in write),
			"value": [
				{k: row.get(k) for k in ("specification_category", "specification_name", "value", "uom", "notes")}
				for row in doc.get(field.fieldname) or []
			] if field.fieldtype == "Table" else doc.get(field.fieldname),
		})
	return {"name": name, "modified": str(doc.modified) if name else None,
		"photos": template_photos(name) if name else [],
		"sections": [s for s in sections if s["fields"]], "status": doc.status,
		"can_write": bool(doc.has_permission("write") if name else frappe.has_permission(DOCTYPE, "create")),
		"can_create": bool(frappe.has_permission(DOCTYPE, "create")),
		"linked_count": domain.get_linked_vehicle_count(name, company=company) if name and frappe.has_permission("Vehicle Master", "read") else None}


@frappe.whitelist(methods=["POST"])
def save_template(values, name=None, modified=None):
	require_access()
	values = frappe.parse_json(values) if isinstance(values, str) else values
	if not isinstance(values, dict):
		frappe.throw(_("Unsupported field"))
	doc = domain._template(name, "write") if name else frappe.new_doc(DOCTYPE)
	if not name:
		doc.check_permission("create")
	if name and str(doc.modified) != str(modified):
		frappe.throw(_("This record changed. Reload it before saving."), frappe.TimestampMismatchError)
	writable = set(get_permitted_fields(DOCTYPE, permission_type="write"))
	for key, value in values.items():
		field = doc.meta.get_field(key)
		if not field or field.read_only or (key not in writable and not (field.fieldtype == "Table" and not field.permlevel)) or field.fieldtype in {"Section Break", "Column Break"}:
			frappe.throw(_("Unsupported field"))
		if field.fieldtype == "Table":
			allowed = {"specification_category", "specification_name", "value", "uom", "notes"}
			if not isinstance(value, list) or any(not isinstance(row, dict) or set(row) - allowed for row in value):
				frappe.throw(_("Unsupported field"))
		elif not isinstance(value, (str, int, float, type(None))):
			frappe.throw(_("Unsupported field"))
		doc.set(key, value)
	doc.save()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def publish_template(name):
	require_access()
	return domain.publish_template(name)


@frappe.whitelist(methods=["POST"])
def create_revision(name):
	require_access()
	return domain.create_revision(name)


@frappe.whitelist(methods=["POST"])
def remove_photo(name, photo, modified):
	require_access()
	doc = domain._template(name, "write")
	if doc.status != "Draft" or doc.published_on:
		frappe.throw(_("Published template revisions are immutable. Create a new revision."))
	if str(doc.modified) != str(modified):
		frappe.throw(_("This record changed. Reload it before saving."), frappe.TimestampMismatchError)
	file = frappe.get_doc("File", photo)
	file.check_permission("delete")
	if file.attached_to_doctype != DOCTYPE or file.attached_to_name != name:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	for field in ASSET_FIELDS:
		if doc.get(field) == file.file_url:
			doc.set(field, None)
	doc.save()
	file.delete()
	return {"modified": str(doc.modified)}


@frappe.whitelist()
def get_linked_vehicles(template, search="", status="", company=None, page=1, page_length=20):
	require_read("Vehicle Master")
	return domain.get_linked_vehicles(template, search, status, company, page, page_length)
