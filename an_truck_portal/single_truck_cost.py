"""Single-VIN LCVs, restricted to a proven one-unit serialized receipt row."""
import hashlib
import json
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import cstr, flt, nowdate, strip_html

from an_truck.services import CUSTOM_FIELD, get_serials_for_row
from an_truck_portal.api.import_file import _require_mutable_import_file

DT = "Landed Cost Voucher"
VEHICLE = "custom_portal_truck_cost_vehicle"
TOKEN = "custom_portal_truck_cost_request"
PAYLOAD = "custom_portal_truck_cost_payload"
SHARED_ROW = "This receipt row contains multiple units or VINs. ERPNext v16 allocates landed cost to the whole receipt row, so a cost for only this VIN cannot be submitted safely."


def _access(import_file):
	vif = _require_mutable_import_file(import_file)
	if vif.status == "Cancelled": frappe.throw(_("Cannot add costs to a cancelled import file."))
	for permission in ("read", "create", "submit"):
		if not frappe.has_permission(DT, permission): frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not all(frappe.get_meta(DT).has_field(f) for f in (VEHICLE,TOKEN,PAYLOAD)):
		frappe.throw(_("Single-truck cost setup is required. Contact your administrator."))
	frappe.get_doc("Company", vif.company).check_permission("read")
	return vif


def _input(data):
	data = frappe.parse_json(data) if isinstance(data, str) else data
	if not isinstance(data, dict): frappe.throw(_("Invalid cost data."))
	try:
		amount = Decimal(str(data.get("amount")))
		if not amount.is_finite() or amount <= 0: raise ValueError
	except (ValueError, InvalidOperation): frappe.throw(_("Enter a positive cost amount."))
	return {"vehicle": cstr(data.get("vehicle")), "amount": str(amount.normalize()),
		"expense_account": cstr(data.get("expense_account")),
		"description": strip_html(cstr(data.get("description"))).strip()[:2000]}


def _hash(data):
	return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _target(vif, vehicle, lock=False):
	vm = frappe.get_doc("Vehicle Master", vehicle, for_update=lock)
	vm.check_permission("read")
	if vm.vehicle_import_file != vif.name or vm.company != vif.company:
		frappe.throw(_("Selected vehicle does not belong to this import file."), frappe.PermissionError)
	if vm.disabled or vm.docstatus == 2 or not vm.purchase_receipt or not vm.purchase_receipt_item:
		frappe.throw(_("Select a vehicle with an active submitted Purchase Receipt item."))
	pr = frappe.get_doc("Purchase Receipt", vm.purchase_receipt, for_update=lock)
	pr.check_permission("read")
	if pr.docstatus != 1 or pr.is_return or pr.company != vif.company or pr.get(CUSTOM_FIELD) != vif.name:
		frappe.throw(_("Select a vehicle with an active submitted Purchase Receipt item."))
	row = next((r for r in pr.items if r.name == vm.purchase_receipt_item), None)
	if not row or row.item_code != vm.item_code or not row.warehouse:
		frappe.throw(_("The vehicle and its Purchase Receipt item do not match."))
	warehouse = frappe.get_doc("Warehouse", row.warehouse)
	warehouse.check_permission("read")
	if warehouse.company != vif.company: frappe.throw(_("The vehicle and its Purchase Receipt item do not match."))
	item = frappe.get_doc("Item", row.item_code)
	item.check_permission("read")
	serials = get_serials_for_row(row)
	reason = ""
	if flt(row.qty) != 1 or flt(row.stock_qty) != 1 or flt(row.rejected_qty) or flt(row.received_qty or row.qty)!=1 or len(serials) != 1:
		reason = SHARED_ROW
	elif not item.is_stock_item or not item.has_serial_no or row.is_fixed_asset or serials[0] != vm.vin:
		reason = "The receipt row must contain exactly the selected truck VIN as one stock unit."
	details = {"vehicle": vm.name, "vin": vm.vin, "item_code": vm.item_code, "item_name": vm.item_name,
		"vehicle_import_file": vif.name, "company": vif.company, "warehouse": row.warehouse,
		"purchase_receipt": pr.name, "purchase_receipt_item": row.name,
		"receipt_currency": pr.currency, "company_currency": frappe.get_cached_value("Company", vif.company, "default_currency"),
		"eligible": not reason, "reason": reason}
	return details, row, reason


def search_vehicles(vehicle_import_file, search="", **kwargs):
	vif = _access(vehicle_import_file)
	return [{"value": r.name, "label": " · ".join(filter(None, [r.vin,r.item_name]))} for r in frappe.get_list(
		"Vehicle Master", fields=["name","vin","item_name"],
		filters={"vehicle_import_file":vif.name,"company":vif.company,"disabled":0,"docstatus":["<",2]},
		or_filters=[["vin","like",f"%{cstr(search)[:100]}%"],["name","like",f"%{cstr(search)[:100]}%"]],
		order_by="vin asc",page_length=30)]


def get_target(vehicle_import_file, vehicle):
	return _target(_access(vehicle_import_file), vehicle)[0]


def _build(vif, data, lock=False):
	target, source, reason = _target(vif, data["vehicle"], lock=lock)
	if reason: frappe.throw(_(reason))
	account = frappe.get_doc("Account", data["expense_account"])
	account.check_permission("read")
	# Match the existing portal's selectable expense-account configuration;
	# the native LCV controller also applies its charge-account/dimension rules.
	if account.company != vif.company or account.disabled or account.is_group or account.root_type != "Expense" or account.account_type == "Stock":
		frappe.throw(_("Select an enabled landed cost expense account for this company."))
	doc = frappe.new_doc(DT)
	doc.update({"company":vif.company,"posting_date":nowdate(),"distribute_charges_based_on":"Distribute Manually",
		CUSTOM_FIELD:vif.name,VEHICLE:target["vehicle"]})
	doc.append("purchase_receipts",{"receipt_document_type":"Purchase Receipt","receipt_document":target["purchase_receipt"]})
	doc.get_items_from_purchase_receipts()
	selected = [r for r in doc.items if r.purchase_receipt_item == source.name]
	if len(selected) != 1: frappe.throw(_("The vehicle and its Purchase Receipt item do not match."))
	doc.set("items",selected)
	description = f"{_('VIN / Chassis Number')}: {target['vin']}"
	if data["description"]: description += " · " + data["description"]
	doc.append("taxes",{"expense_account":account.name,"amount":float(data["amount"]),"description":description})
	# Native currency/rate, tax, account, dimension and reference validation.
	doc.run_method("validate")
	if flt(doc.total_taxes_and_charges) <= 0: frappe.throw(_("Enter a positive cost amount."))
	doc.items[0].applicable_charges = doc.total_taxes_and_charges
	doc.validate_applicable_charges_for_item()
	summary = {**target,"amount":doc.taxes[0].amount,"currency":doc.taxes[0].account_currency,
		"company_amount":doc.total_taxes_and_charges,"exchange_rate":doc.taxes[0].exchange_rate,
		"expense_account":account.name,"description":data["description"],"posting_date":doc.posting_date}
	return doc, summary


def preview(vehicle_import_file, data):
	vif = _access(vehicle_import_file)
	_voucher, summary = _build(vif,_input(data))
	return {"summary":summary,"confirmation":_hash(summary)}


def create(vehicle_import_file, data, request_key, confirmation):
	vif = _access(vehicle_import_file)  # locks this import file for the whole transaction
	data = _input(data)
	if not request_key or len(cstr(request_key)) > 100: frappe.throw(_("Reopen the cost popup and try again."))
	token = _hash([vif.name,frappe.session.user,cstr(request_key)])
	payload = _hash(data)
	name = frappe.db.get_value(DT,{TOKEN:token},"name",for_update=True)
	if name:
		doc = frappe.get_doc(DT,name,for_update=True)
		doc.check_permission("read"); doc.check_permission("submit")
		if doc.get(PAYLOAD) != payload: frappe.throw(_("This cost request was already used with different data."))
		if doc.docstatus != 1: frappe.throw(_("This cost request is not submitted. Review its existing voucher before starting a new cost."))
		return {"name":doc.name,"doctype":DT,"docstatus":doc.docstatus}
	doc, summary = _build(vif,data,lock=True)
	if not confirmation or confirmation != _hash(summary): frappe.throw(_("Cost details changed. Review the confirmation again."))
	doc.set(TOKEN,token);doc.set(PAYLOAD,payload)
	frappe.db.savepoint("single_truck_cost")
	try:
		doc.insert()
		doc.submit()
	except Exception:
		frappe.db.rollback(save_point="single_truck_cost")
		raise
	return {"name":doc.name,"doctype":DT,"docstatus":doc.docstatus}


def validate_single_truck_cost(doc, method=None):
	"""Protect targeted vouchers through Desk/API as well; bulk LCVs are untouched."""
	previous = doc.get_doc_before_save()
	if not doc.get(VEHICLE):
		if doc.get(TOKEN) or previous and previous.get(VEHICLE): frappe.throw(_("Single-truck cost audit links cannot be changed."))
		return
	vif = frappe.get_doc("Vehicle Import File",doc.get(CUSTOM_FIELD))
	vif.check_permission("read")
	_details, source, reason = _target(vif,doc.get(VEHICLE))
	if reason: frappe.throw(_(reason))
	if (doc.company != vif.company or doc.distribute_charges_based_on != "Distribute Manually"
		or len(doc.purchase_receipts)!=1 or len(doc.items)!=1
		or doc.purchase_receipts[0].receipt_document_type!="Purchase Receipt"
		or doc.purchase_receipts[0].receipt_document!=source.parent
		or doc.items[0].receipt_document_type!="Purchase Receipt" or doc.items[0].receipt_document!=source.parent
		or doc.items[0].purchase_receipt_item!=source.name or doc.items[0].item_code!=source.item_code or flt(doc.items[0].qty)!=1):
		frappe.throw(_("A single-truck cost must target only its original one-unit receipt item."))
	# Runs after the native controller, whose manual allocation is assigned by
	# the builder on preview and enforced again by ERPNext at submission.
	if previous:
		if any(previous.get(f)!=doc.get(f) for f in (VEHICLE,TOKEN,PAYLOAD)):
			frappe.throw(_("Single-truck cost audit links cannot be changed."))
