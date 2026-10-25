"""Permission-aware warranty views for the AN Truck portal.

The warranty domain remains owned by ``an_truck``.  This module is deliberately a
thin, read-only presentation adapter: it reuses the existing DocTypes and reporting
rules and never bypasses document or Company permissions.
"""

from urllib.parse import quote

import frappe
from an_truck.warranty.access import is_provider_user
from an_truck.warranty.timezone import get_company_local_date
from frappe import _
from frappe.core.doctype.user_permission.user_permission import get_permitted_documents
from frappe.model import get_permitted_fields
from frappe.utils import add_days, cint, getdate

from an_truck_portal.access import require_access

OPEN_CLAIM_STATES = {
	"Draft",
	"Submitted by Provider",
	"Under Internal Review",
	"Need More Information",
	"Approved",
	"Partially Approved",
	"Repair In Progress",
	"Repair Completed",
	"Final Documents Submitted",
}
AWAITING_APPROVAL_STATES = {"Submitted by Provider", "Under Internal Review"}

MASTER_RESOURCES = {
	"providers": {
		"doctype": "Warranty Provider",
		"title": "Warranty Providers",
		"fields": [
			"name",
			"provider_name",
			"provider_name_arabic",
			"status",
			"active",
			"city",
			"phone",
			"email",
			"modified",
		],
		"search": ["name", "provider_name", "provider_name_arabic", "commercial_registration"],
	},
	"provider-branches": {
		"doctype": "Warranty Provider Branch",
		"title": "Provider Branches",
		"fields": [
			"name",
			"warranty_provider",
			"branch_name",
			"branch_name_arabic",
			"branch_code",
			"active",
			"city",
			"phone",
			"email",
			"modified",
		],
		"search": ["name", "branch_name", "branch_name_arabic", "branch_code", "city"],
	},
	"provider-contracts": {
		"doctype": "Warranty Provider Contract",
		"title": "Provider Contracts",
		"fields": [
			"name",
			"contract_number",
			"warranty_provider",
			"contract_type",
			"status",
			"start_date",
			"end_date",
			"auto_renewal",
			"renewal_date",
			"modified",
		],
		"search": ["name", "contract_number", "warranty_provider"],
	},
	"coverage-templates": {
		"doctype": "Warranty Coverage Template",
		"title": "Coverage Templates",
		"fields": ["name", "template_name", "duration", "duration_unit", "active", "modified"],
		"search": ["name", "template_name"],
	},
	"coverage-categories": {
		"doctype": "Warranty Coverage Category",
		"title": "Coverage Categories",
		"fields": ["name", "category_name", "category_name_arabic", "active", "description", "modified"],
		"search": ["name", "category_name", "category_name_arabic"],
	},
}

PROVIDER_PORTAL_FIELDS = (
	"provider_name",
	"commercial_registration",
	"tax_number",
	"mobile",
	"phone",
	"email",
	"website",
	"primary_address",
	"city",
	"country",
	"notes",
)

PROVIDER_BRANCH_PORTAL_FIELDS = (
	"branch_name",
	"address",
	"city",
	"google_maps_url",
	"contact_person",
	"mobile",
	"email",
	"working_hours",
)


def _require_internal(doctype=None):
	require_access()
	if is_provider_user():
		frappe.throw(
			_("You are not permitted to access internal warranty information."), frappe.PermissionError
		)
	if doctype and not frappe.has_permission(doctype, "read"):
		frappe.throw(_("Not permitted to read {0}.").format(_(doctype)), frappe.PermissionError)


def _company_filter(company):
	permitted = set(get_permitted_documents("Company") or [])
	if company and permitted and company not in permitted:
		frappe.throw(_("You are not permitted to access this Company."), frappe.PermissionError)
	return company


def _page_values(page, page_length):
	page = max(cint(page), 1)
	page_length = min(max(cint(page_length), 1), 100)
	return page, page_length


def _display_name(doctype, name):
	if not name:
		return None
	field = {
		"Customer": "customer_name",
		"Warranty Provider": "provider_name",
		"Warranty Provider Branch": "branch_name",
	}.get(doctype)
	return frappe.get_cached_value(doctype, name, field) if field else name


@frappe.whitelist(methods=["GET"])
def get_dashboard(company=None):
	_require_internal("Vehicle Warranty")
	if not frappe.has_permission("Warranty Claim", "read"):
		frappe.throw(_("Not permitted to read Warranty Claim."), frappe.PermissionError)
	company = _company_filter(company)
	companies = [company] if company else frappe.get_list("Company", pluck="name")
	companies = [row for row in companies if frappe.db.get_value("Company", row, "custom_warranty_timezone")]
	warranty_filters = (
		{"company": ["in", companies]} if companies else {"name": "__no_accessible_warranty_records__"}
	)
	claim_filters = {**warranty_filters, "docstatus": ["<", 2]}
	expiring_30 = expiring_7 = 0
	for company_name in companies:
		today = get_company_local_date(company_name)
		base = {"company": company_name, "status": "Active"}
		expiring_30 += frappe.db.count(
			"Vehicle Warranty", {**base, "warranty_expiry_date": ["between", [today, add_days(today, 30)]]}
		)
		expiring_7 += frappe.db.count(
			"Vehicle Warranty", {**base, "warranty_expiry_date": ["between", [today, add_days(today, 7)]]}
		)

	status_rows = frappe.get_list(
		"Warranty Claim",
		filters=claim_filters,
		fields=["custom_claim_status as status", {"COUNT": "name", "as": "count"}],
		group_by="custom_claim_status",
		page_length=0,
	)
	status_counts = {row.status: cint(row.count) for row in status_rows}

	return {
		"cards": [
			{
				"label": _("Active Warranties"),
				"value": frappe.db.count("Vehicle Warranty", {**warranty_filters, "status": "Active"}),
			},
			{"label": _("Expiring in 30 Days"), "value": expiring_30},
			{"label": _("Expiring in 7 Days"), "value": expiring_7},
			{
				"label": _("Expired Warranties"),
				"value": frappe.db.count("Vehicle Warranty", {**warranty_filters, "status": "Expired"}),
			},
			{
				"label": _("Open Claims"),
				"value": sum(status_counts.get(state, 0) for state in OPEN_CLAIM_STATES),
			},
			{
				"label": _("Claims Awaiting Approval"),
				"value": sum(status_counts.get(state, 0) for state in AWAITING_APPROVAL_STATES),
			},
		],
		"recent_warranties": frappe.get_list(
			"Vehicle Warranty",
			filters=warranty_filters,
			fields=[
				"name",
				"vin",
				"vehicle_master",
				"customer",
				"warranty_provider",
				"warranty_expiry_date",
				"status",
				"modified",
			],
			order_by="modified desc",
			page_length=8,
		),
		"recent_claims": frappe.get_list(
			"Warranty Claim",
			filters=claim_filters,
			fields=[
				"name",
				"serial_no as vin",
				"custom_vehicle_warranty as vehicle_warranty",
				"customer",
				"custom_warranty_provider as provider",
				"complaint_date as claim_date",
				"custom_claim_status as status",
				"modified",
			],
			order_by="modified desc",
			page_length=8,
		),
	}


@frappe.whitelist(methods=["GET"])
def list_warranties(
	search=None,
	status=None,
	provider=None,
	expiry_from=None,
	expiry_to=None,
	company=None,
	page=1,
	page_length=20,
):
	_require_internal("Vehicle Warranty")
	company = _company_filter(company)
	page, page_length = _page_values(page, page_length)
	filters = {}
	if company:
		filters["company"] = company
	if status:
		filters["status"] = status
	if provider:
		filters["warranty_provider"] = provider
	if expiry_from:
		filters["warranty_expiry_date"] = [">=", getdate(expiry_from)]
	if expiry_to:
		if "warranty_expiry_date" in filters:
			filters["warranty_expiry_date"] = ["between", [getdate(expiry_from), getdate(expiry_to)]]
		else:
			filters["warranty_expiry_date"] = ["<=", getdate(expiry_to)]
	or_filters = None
	if search:
		term = f"%{search.strip()}%"
		or_filters = [
			["Vehicle Warranty", field, "like", term]
			for field in ("name", "vin", "vehicle_master", "customer")
		]
	rows = frappe.get_list(
		"Vehicle Warranty",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name",
			"vin",
			"vehicle_master",
			"vehicle_model",
			"customer",
			"warranty_provider",
			"warranty_start_date",
			"warranty_expiry_date",
			"status",
			"modified",
		],
		order_by="warranty_start_date desc, modified desc",
		start=(page - 1) * page_length,
		page_length=page_length + 1,
	)
	warranty_names = [row.name for row in rows]
	branches_by_warranty = {}
	mileage_by_warranty = {}
	if warranty_names:
		for coverage in frappe.get_all(
			"Vehicle Warranty Coverage Item",
			filters={"parent": ["in", warranty_names], "parenttype": "Vehicle Warranty"},
			fields=["parent", "mileage_limit"],
		):
			if coverage.mileage_limit:
				mileage_by_warranty[coverage.parent] = max(
					coverage.mileage_limit, mileage_by_warranty.get(coverage.parent, 0)
				)
	if warranty_names and frappe.has_permission("Warranty Claim", "read"):
		for claim in frappe.get_list(
			"Warranty Claim",
			filters={"custom_vehicle_warranty": ["in", warranty_names], "docstatus": ["<", 2]},
			fields=["custom_vehicle_warranty", "custom_warranty_provider_branch"],
			page_length=0,
		):
			if claim.custom_warranty_provider_branch:
				branches_by_warranty.setdefault(claim.custom_vehicle_warranty, set()).add(
					claim.custom_warranty_provider_branch
				)
	for row in rows:
		row.customer_name = _display_name("Customer", row.customer)
		row.provider_name = _display_name("Warranty Provider", row.warranty_provider)
		row.provider_branch = ", ".join(sorted(branches_by_warranty.get(row.name, set()))) or None
		row.mileage_limit = mileage_by_warranty.get(row.name)
	return {"rows": rows[:page_length], "page": page, "has_more": len(rows) > page_length}


@frappe.whitelist(methods=["GET"])
def get_warranty(name):
	_require_internal("Vehicle Warranty")
	doc = frappe.get_doc("Vehicle Warranty", name)
	doc.check_permission("read")
	claims = []
	if frappe.has_permission("Warranty Claim", "read"):
		claims = frappe.get_list(
			"Warranty Claim",
			filters={"custom_vehicle_warranty": doc.name, "docstatus": ["<", 2]},
			fields=[
				"name",
				"complaint_date as claim_date",
				"custom_claim_status as status",
				"custom_warranty_provider_branch as provider_branch",
				"custom_internal_decision as coverage_decision",
			],
			order_by="complaint_date desc, modified desc",
		)
	provider_branches = sorted({row.provider_branch for row in claims if row.provider_branch})
	return {
		"warranty": {
			"name": doc.name,
			"vin": doc.vin,
			"vehicle_master": doc.vehicle_master,
			"vehicle": doc.vehicle,
			"vehicle_model": doc.vehicle_model,
			"item_code": doc.item_code,
			"company": doc.company,
			"customer": doc.customer,
			"customer_name": _display_name("Customer", doc.customer),
			"provider": doc.warranty_provider,
			"provider_name": _display_name("Warranty Provider", doc.warranty_provider),
			"provider_branch": ", ".join(provider_branches) or None,
			"provider_contract": doc.provider_contract,
			"coverage_template": doc.coverage_template,
			"delivery_note": doc.delivery_note,
			"sales_invoice": doc.sales_invoice,
			"delivery_date": doc.delivery_date,
			"start_date": doc.warranty_start_date,
			"expiry_date": doc.warranty_expiry_date,
			"status": doc.status,
			"activation_source": doc.activation_source,
			"renewal_of": doc.renewal_of,
			"is_extension": doc.is_extension,
			"currency": doc.currency,
			"notes": doc.notes,
		},
		"coverage": [
			{
				"category": row.coverage_category,
				"description": row.description,
				"covered": row.covered,
				"coverage_limit": row.coverage_limit,
				"mileage_limit": row.mileage_limit,
				"conditions": row.conditions,
				"exclusions": row.exclusions,
			}
			for row in doc.coverage_snapshot
		],
		"claims": claims,
		"certificate_url": "/printview?doctype=Vehicle%20Warranty&name={0}&format=Vehicle%20Warranty%20Certificate".format(
			quote(doc.name)
		),
	}


@frappe.whitelist(methods=["GET"])
def list_claims(search=None, status=None, provider=None, company=None, page=1, page_length=20):
	_require_internal("Warranty Claim")
	company = _company_filter(company)
	page, page_length = _page_values(page, page_length)
	filters = {"docstatus": ["<", 2]}
	if company:
		filters["company"] = company
	if status:
		filters["custom_claim_status"] = status
	if provider:
		filters["custom_warranty_provider"] = provider
	or_filters = None
	if search:
		term = f"%{search.strip()}%"
		or_filters = [
			["Warranty Claim", field, "like", term]
			for field in ("name", "serial_no", "customer", "custom_vehicle_warranty")
		]
	rows = frappe.get_list(
		"Warranty Claim",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name",
			"serial_no as vin",
			"item_code",
			"custom_vehicle_master as vehicle_master",
			"custom_vehicle_warranty as vehicle_warranty",
			"customer",
			"custom_warranty_provider as provider",
			"custom_warranty_provider_branch as provider_branch",
			"complaint_date as claim_date",
			"custom_claim_status as status",
			"custom_provider_recommendation as provider_decision",
			"custom_internal_decision as coverage_decision",
			"modified",
		],
		order_by="complaint_date desc, modified desc",
		start=(page - 1) * page_length,
		page_length=page_length + 1,
	)
	for row in rows:
		row.customer_name = _display_name("Customer", row.customer)
		row.provider_name = _display_name("Warranty Provider", row.provider)
		row.branch_name = _display_name("Warranty Provider Branch", row.provider_branch)
	return {"rows": rows[:page_length], "page": page, "has_more": len(rows) > page_length}


def _claim_value(doc, allowed, fieldname):
	return doc.get(fieldname) if fieldname in allowed else None


@frappe.whitelist(methods=["GET"])
def get_claim(name):
	_require_internal("Warranty Claim")
	doc = frappe.get_doc("Warranty Claim", name)
	doc.check_permission("read")
	allowed = set(get_permitted_fields("Warranty Claim", permission_type="read"))
	data = {
		"name": doc.name,
		"vin": doc.serial_no,
		"vehicle_master": _claim_value(doc, allowed, "custom_vehicle_master"),
		"vehicle_warranty": _claim_value(doc, allowed, "custom_vehicle_warranty"),
		"item_code": doc.item_code,
		"customer": doc.customer,
		"customer_name": _display_name("Customer", doc.customer),
		"company": doc.company,
		"provider": _claim_value(doc, allowed, "custom_warranty_provider"),
		"provider_branch": _claim_value(doc, allowed, "custom_warranty_provider_branch"),
		"claim_date": doc.complaint_date,
		"failure_date": _claim_value(doc, allowed, "custom_failure_date"),
		"status": _claim_value(doc, allowed, "custom_claim_status") or doc.status,
		"complaint": doc.complaint,
		"inspection_date": _claim_value(doc, allowed, "custom_inspection_date"),
		"technician": _claim_value(doc, allowed, "custom_technician_name"),
		"inspection": _claim_value(doc, allowed, "custom_inspection_details"),
		"diagnosis": _claim_value(doc, allowed, "custom_diagnosis"),
		"root_cause": _claim_value(doc, allowed, "custom_root_cause"),
		"eligibility": doc.warranty_amc_status,
		"provider_decision": _claim_value(doc, allowed, "custom_provider_recommendation"),
		"provider_reason": _claim_value(doc, allowed, "custom_provider_reason"),
		"coverage_decision": _claim_value(doc, allowed, "custom_internal_decision"),
		"decision_reason": _claim_value(doc, allowed, "custom_internal_decision_reason"),
		"approval_date": _claim_value(doc, allowed, "custom_approval_date"),
		"currency": _claim_value(doc, allowed, "custom_currency"),
		"total_repair_cost": _claim_value(doc, allowed, "custom_total_repair_cost"),
		"warranty_covered_amount": _claim_value(doc, allowed, "custom_warranty_covered_amount"),
		"customer_payable_amount": _claim_value(doc, allowed, "custom_customer_payable_amount"),
		"provider_claim_amount": _claim_value(doc, allowed, "custom_provider_claim_amount"),
		"approved_provider_amount": _claim_value(doc, allowed, "custom_approved_provider_claim_amount"),
	}
	return {
		"claim": data,
		"parts": [
			{
				"category": row.coverage_category,
				"item": row.item,
				"part_number": row.part_number,
				"description": row.description,
				"qty": row.qty,
				"uom": row.uom,
				"unit_cost": row.unit_cost,
				"total": row.total_cost,
				"coverage_status": row.coverage_status,
				"covered_amount": row.covered_amount,
				"customer_payable": row.customer_payable_amount,
			}
			for row in doc.custom_parts
		]
		if "custom_parts" in allowed
		else [],
		"services": [
			{
				"category": row.coverage_category,
				"service_type": row.service_type,
				"description": row.description,
				"hours": row.hours,
				"rate": row.rate,
				"total": row.amount,
				"coverage_status": row.coverage_status,
				"covered_amount": row.covered_amount,
				"customer_payable": row.customer_payable_amount,
			}
			for row in doc.custom_services
		]
		if "custom_services" in allowed
		else [],
		"documents": [
			{
				"type": row.document_type,
				"file": row.file,
				"invoice_number": row.invoice_number,
				"invoice_date": row.invoice_date,
				"invoice_amount": row.invoice_amount,
				"vat_amount": row.vat_amount,
				"total": row.total_including_vat,
				"notes": row.notes,
			}
			for row in doc.custom_documents
		]
		if "custom_documents" in allowed
		else [],
	}


@frappe.whitelist(methods=["GET"])
def list_master(resource, search=None, page=1, page_length=20):
	config = MASTER_RESOURCES.get(resource)
	if not config:
		frappe.throw(_("Unsupported warranty resource."), frappe.ValidationError)
	_require_internal(config["doctype"])
	page, page_length = _page_values(page, page_length)
	or_filters = None
	if search:
		term = f"%{search.strip()}%"
		or_filters = [[config["doctype"], field, "like", term] for field in config["search"]]
	rows = frappe.get_list(
		config["doctype"],
		or_filters=or_filters,
		fields=config["fields"],
		order_by="modified desc",
		start=(page - 1) * page_length,
		page_length=page_length + 1,
	)
	if resource == "providers":
		for row in rows:
			row.can_write = bool(frappe.has_permission(config["doctype"], "write", row.name))
	return {
		"doctype": config["doctype"],
		"title": _(config["title"]),
		"rows": rows[:page_length],
		"page": page,
		"has_more": len(rows) > page_length,
	}


@frappe.whitelist(methods=["GET"])
def get_provider_form(name=None):
	_require_internal("Warranty Provider")
	if not frappe.has_permission("Country", "read"):
		frappe.throw(_("Not permitted to read Country."), frappe.PermissionError)
	countries = [
		{"value": country, "label": country}
		for country in frappe.get_list("Country", pluck="name", order_by="name asc", page_length=0)
	]
	if not name:
		return {
			"record": {fieldname: "" for fieldname in PROVIDER_PORTAL_FIELDS},
			"modified": None,
			"can_write": bool(frappe.has_permission("Warranty Provider", "create")),
			"countries": countries,
		}
	doc = frappe.get_doc("Warranty Provider", name)
	doc.check_permission("read")
	return {
		"record": {fieldname: doc.get(fieldname) or "" for fieldname in PROVIDER_PORTAL_FIELDS},
		"modified": str(doc.modified),
		"can_write": bool(frappe.has_permission("Warranty Provider", "write", doc=doc)),
		"countries": countries,
	}


@frappe.whitelist(methods=["POST"])
def save_provider(data, name=None, modified=None):
	_require_internal("Warranty Provider")
	data = frappe.parse_json(data) if isinstance(data, str) else data
	if not isinstance(data, dict) or set(data) - set(PROVIDER_PORTAL_FIELDS):
		frappe.throw(_("Unsupported field."), frappe.ValidationError)
	doc = frappe.get_doc("Warranty Provider", name) if name else frappe.new_doc("Warranty Provider")
	permission = "write" if name else "create"
	if not frappe.has_permission("Warranty Provider", permission, doc=doc):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if name:
		doc.check_permission("read")
		if str(doc.modified) != str(modified):
			frappe.throw(
				_("This record changed. Reload it before saving."),
				frappe.TimestampMismatchError,
			)
	else:
		# Status and Active are intentionally hidden from the portal form. New
		# providers receive the DocType's safe operational defaults.
		doc.status = "Active"
		doc.active = 1
	for fieldname in PROVIDER_PORTAL_FIELDS:
		if fieldname not in data:
			continue
		value = data[fieldname]
		if not isinstance(value, (str, int, float, type(None))):
			frappe.throw(_("Unsupported field."), frappe.ValidationError)
		doc.set(fieldname, value.strip() if isinstance(value, str) else value)
	if not doc.provider_name:
		frappe.throw(_("Provider Name is required."), frappe.MandatoryError)
	doc.save()
	return {"name": doc.name, "modified": str(doc.modified)}


def _get_provider_for_branch(provider):
	if not provider:
		frappe.throw(_("Warranty Provider is required."), frappe.MandatoryError)
	doc = frappe.get_doc("Warranty Provider", provider)
	doc.check_permission("read")
	return doc


@frappe.whitelist(methods=["GET"])
def get_provider_branch_form(provider, name=None):
	_require_internal("Warranty Provider Branch")
	_get_provider_for_branch(provider)
	if not name:
		return {
			"record": {fieldname: "" for fieldname in PROVIDER_BRANCH_PORTAL_FIELDS},
			"modified": None,
			"can_write": bool(frappe.has_permission("Warranty Provider Branch", "create")),
		}

	doc = frappe.get_doc("Warranty Provider Branch", name)
	doc.check_permission("read")
	if doc.warranty_provider != provider:
		frappe.throw(_("This branch does not belong to the selected Warranty Provider."), frappe.PermissionError)
	return {
		"record": {fieldname: doc.get(fieldname) or "" for fieldname in PROVIDER_BRANCH_PORTAL_FIELDS},
		"modified": str(doc.modified),
		"can_write": bool(frappe.has_permission("Warranty Provider Branch", "write", doc=doc)),
	}


@frappe.whitelist(methods=["POST"])
def save_provider_branch(provider, data, name=None, modified=None):
	_require_internal("Warranty Provider Branch")
	_get_provider_for_branch(provider)
	data = frappe.parse_json(data) if isinstance(data, str) else data
	if not isinstance(data, dict) or set(data) - set(PROVIDER_BRANCH_PORTAL_FIELDS):
		frappe.throw(_("Unsupported field."), frappe.ValidationError)

	doc = (
		frappe.get_doc("Warranty Provider Branch", name)
		if name
		else frappe.new_doc("Warranty Provider Branch")
	)
	if not name:
		doc.warranty_provider = provider
		doc.active = 1
	permission = "write" if name else "create"
	if not frappe.has_permission("Warranty Provider Branch", permission, doc=doc):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if name:
		doc.check_permission("read")
		if doc.warranty_provider != provider:
			frappe.throw(
				_("This branch does not belong to the selected Warranty Provider."),
				frappe.PermissionError,
			)
		if str(doc.modified) != str(modified):
			frappe.throw(
				_("This record changed. Reload it before saving."),
				frappe.TimestampMismatchError,
			)
	for fieldname in PROVIDER_BRANCH_PORTAL_FIELDS:
		if fieldname not in data:
			continue
		value = data[fieldname]
		if not isinstance(value, (str, int, float, type(None))):
			frappe.throw(_("Unsupported field."), frappe.ValidationError)
		doc.set(fieldname, value.strip() if isinstance(value, str) else value)
	if not doc.branch_name:
		frappe.throw(_("Branch Name is required."), frappe.MandatoryError)
	if not doc.city:
		frappe.throw(_("City is required."), frappe.MandatoryError)
	doc.save()
	return {"name": doc.name, "modified": str(doc.modified)}


@frappe.whitelist(methods=["GET"])
def get_master(resource, name):
	config = MASTER_RESOURCES.get(resource)
	if not config:
		frappe.throw(_("Unsupported warranty resource."), frappe.ValidationError)
	_require_internal(config["doctype"])
	doc = frappe.get_doc(config["doctype"], name)
	doc.check_permission("read")
	allowed = set(get_permitted_fields(config["doctype"], permission_type="read"))
	fields = []
	for field in doc.meta.fields:
		if (
			field.fieldname not in allowed
			or field.hidden
			or field.fieldtype in {"Section Break", "Column Break", "Tab Break", "HTML", "Button"}
		):
			continue
		value = doc.get(field.fieldname)
		if field.fieldtype == "Table" and field.options:
			child_meta = frappe.get_meta(field.options)
			child_fields = [
				row
				for row in child_meta.fields
				if not row.hidden
				and row.fieldtype not in {"Section Break", "Column Break", "Tab Break", "HTML", "Button"}
			]
			value = [
				{child.fieldname: row.get(child.fieldname) for child in child_fields} for row in (value or [])
			]
		fields.append(
			{
				"fieldname": field.fieldname,
				"label": _(field.label),
				"fieldtype": field.fieldtype,
				"value": value,
			}
		)
	result = {"doctype": config["doctype"], "title": _(config["title"]), "name": doc.name, "fields": fields}
	if resource == "providers":
		result["can_write"] = bool(frappe.has_permission("Warranty Provider", "write", doc=doc))
		branches = frappe.get_list(
			"Warranty Provider Branch",
			filters={"warranty_provider": doc.name},
			fields=[
				"name",
				"branch_name",
				"address",
				"city",
				"google_maps_url",
				"contact_person",
				"mobile",
				"email",
				"working_hours",
			],
			order_by="modified desc",
			page_length=0,
		)
		for branch in branches:
			branch.can_write = bool(
				frappe.has_permission("Warranty Provider Branch", "write", branch.name)
			)
		result["branches"] = branches
		result["can_create_branch"] = bool(
			frappe.has_permission("Warranty Provider Branch", "create")
		)
	return result
