import frappe
from frappe import _
from an_truck import financial_vouchers as domain
from an_truck_portal.access import require_access


@frappe.whitelist(methods=["GET"])
def get_options():
	require_access()
	return domain.options()


@frappe.whitelist(methods=["GET"])
def list_vouchers(search="", direction="", status="", from_date=None, to_date=None, page=1, page_length=20):
	require_access()
	return domain.list_vouchers(search, direction, status, from_date, to_date, page, page_length)


@frappe.whitelist(methods=["GET"])
def get_voucher(name):
	require_access()
	return domain.details(domain.record(name))


@frappe.whitelist(methods=["GET"])
def party_options(party_type, search="", page=1):
	require_access()
	if not frappe.has_permission(domain.DT, "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return domain.parties(party_type, search, page)


@frappe.whitelist(methods=["GET"])
def get_outstanding(party_type, party, direction, date=None):
	require_access()
	if not frappe.has_permission(domain.DT, "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return domain.outstanding(party_type, party, direction, date)


@frappe.whitelist(methods=["POST"])
def preview(data, name=None):
	require_access()
	if not name and not frappe.has_permission(domain.DT, "create"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	doc = domain.build(frappe.parse_json(data) if isinstance(data, str) else data,
		domain.record(name, "write") if name else None)
	return {key: doc.get(key) for key in ("party_name", "paid_amount", "received_amount", "paid_from_account_currency",
		"paid_to_account_currency", "source_exchange_rate", "target_exchange_rate", "total_allocated_amount", "unallocated_amount")}


@frappe.whitelist(methods=["POST"])
def save_voucher(data, name=None, modified=None, request_key=None):
	require_access()
	return domain.save(data, name, modified, request_key)


@frappe.whitelist(methods=["POST"])
def action(name, action, modified=None):
	require_access()
	return domain.act(name, action, modified)


@frappe.whitelist(methods=["GET"])
def download_pdf(name, language=None):
	require_access()
	doc = domain.record(name, "print")
	from frappe.www.printview import validate_print
	validate_print(doc)
	with domain.print_language(domain.language(language)):
		pdf = frappe.get_print(domain.DT, name, domain.FORMAT, as_pdf=True, no_letterhead=1, pdf_generator="chrome")
	frappe.local.response.update({"filename": f"{doc.name}.pdf", "filecontent": pdf, "type": "download", "content_type": "application/pdf", "display_content_as": "attachment"})
