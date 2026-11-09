"""Native single-VIN costing: unit-row LCV or selected-serial revaluation."""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from math import isfinite

import frappe
from frappe import _
from frappe.utils import cstr, flt, now, nowdate, nowtime, strip_html

from an_truck.services import CUSTOM_FIELD, get_serials_for_row
from an_truck_portal.api.import_file import _require_mutable_import_file

DT = "Landed Cost Voucher"
REVALUATION = "Stock Reconciliation"
VEHICLE = "custom_portal_truck_cost_vehicle"
TOKEN = "custom_portal_truck_cost_request"
PAYLOAD = "custom_portal_truck_cost_payload"
SHARED_ROW = "This receipt row contains multiple units or VINs. ERPNext v16 allocates landed cost to the whole receipt row, so a cost for only this VIN cannot be submitted safely."


def _access(import_file):
	vif = _require_mutable_import_file(import_file)
	if vif.status == "Cancelled": frappe.throw(_("Cannot add costs to a cancelled import file."))
	frappe.get_doc("Company", vif.company).check_permission("read")
	return vif


def _document_access(doctype):
	for permission in ("read","create","submit"):
		if not frappe.has_permission(doctype,permission): frappe.throw(_("Not permitted"),frappe.PermissionError)
	fields = [VEHICLE,TOKEN,PAYLOAD,CUSTOM_FIELD]
	if doctype==REVALUATION:
		fields.extend(["custom_portal_truck_cost_receipt","custom_portal_truck_cost_receipt_item",
			"custom_portal_truck_cost_amount","custom_portal_truck_cost_description"])
	if not all(frappe.get_meta(doctype).has_field(f) for f in fields):
		frappe.throw(_("Single-truck cost setup is required. Contact your administrator."))


def _input(data):
	data = frappe.parse_json(data) if isinstance(data, str) else data
	if not isinstance(data, dict): frappe.throw(_("Invalid cost data."))
	try:
		amount = Decimal(str(data.get("amount")))
		if not amount.is_finite() or amount <= 0 or not isfinite(float(amount)): raise ValueError
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
	one_unit = flt(row.qty)==1 and flt(row.stock_qty)==1 and not flt(row.rejected_qty) and flt(row.received_qty or row.qty)==1 and len(serials)==1
	reason,doctype = "",DT if one_unit else REVALUATION
	if not item.is_stock_item or not item.has_serial_no or row.is_fixed_asset or vm.vin not in serials:
		reason = "The receipt row must contain exactly the selected truck VIN as one stock unit."
	details = {"vehicle": vm.name, "vin": vm.vin, "item_code": vm.item_code, "item_name": vm.item_name,
		"vehicle_import_file": vif.name, "company": vif.company, "warehouse": row.warehouse,
		"purchase_receipt": pr.name, "purchase_receipt_item": row.name,
		"receipt_currency": pr.currency, "company_currency": frappe.get_cached_value("Company", vif.company, "default_currency"),
		"eligible": not reason, "reason": reason,"doctype":doctype}
	if doctype==REVALUATION and not reason:
		try: details.update(_serial_quote(vm,item,lock))
		except frappe.ValidationError as exc: reason = str(exc)
		details.update(eligible=not reason,reason=reason)
	return details, row, reason


def _serial_quote(vm,item,lock=False):
	from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import get_available_serial_nos
	from erpnext.stock.utils import get_incoming_rate
	if not item.use_serial_no_wise_valuation: raise frappe.ValidationError("Serial No Wise Valuation must be enabled for this item.")
	if vm.vehicle_status in ("Sold","Delivered","Under Maintenance") or any(frappe.db.exists(dt,
		{"custom_vehicle_master":vm.name,"docstatus":1}) for dt in ("Sales Invoice Item","Delivery Note Item")):
		raise frappe.ValidationError("Sold or delivered trucks cannot use serial revaluation.")
	if frappe.db.exists("Serial and Batch Entry",{"serial_no":vm.vin,"qty":["<",0],"is_cancelled":0,
		"docstatus":1,"voucher_type":["in",["Sales Invoice","Delivery Note"]]}):
		raise frappe.ValidationError("Sold or delivered trucks cannot use serial revaluation.")
	serial = frappe.get_doc("Serial No",vm.vin,for_update=lock)
	serial.check_permission("read")
	if serial.item_code!=vm.item_code or serial.company!=vm.company or not serial.warehouse:
		raise frappe.ValidationError("The selected VIN must be on hand in a company warehouse.")
	warehouse = frappe.get_doc("Warehouse",serial.warehouse)
	warehouse.check_permission("read")
	if warehouse.company!=vm.company: raise frappe.ValidationError("The selected VIN must be on hand in a company warehouse.")
	available = get_available_serial_nos(frappe._dict(item_code=vm.item_code,warehouse=warehouse.name,
		serial_nos=[vm.vin],check_serial_nos=True,posting_datetime=now()))
	if len(available)!=1 or available[0].serial_no!=vm.vin:
		raise frappe.ValidationError("The selected VIN must be on hand in a company warehouse.")
	rate = get_incoming_rate({"item_code":vm.item_code,"warehouse":warehouse.name,"serial_no":vm.vin,
		"posting_date":nowdate(),"posting_time":nowtime(),"qty":-1,"company":vm.company})
	from an_truck.serial_vehicle_cost import valuation_basis
	basis = valuation_basis(vm)
	if basis is None: basis = frappe.db.get_value("Purchase Receipt Item",vm.purchase_receipt_item,"valuation_rate")
	if rate is None or abs(flt(basis)-flt(rate))>0.01:
		raise frappe.ValidationError("The VIN has other valuation adjustments. Review its source stock documents first.")
	return {"warehouse":warehouse.name,"current_valuation":flt(rate)}


def search_vehicles(vehicle_import_file, search="", **kwargs):
	vif = _access(vehicle_import_file)
	if not any(all(frappe.has_permission(dt,p) for p in ("read","create","submit")) for dt in (DT,REVALUATION)):
		frappe.throw(_("Not permitted"),frappe.PermissionError)
	return [{"value": r.name, "label": " · ".join(filter(None, [r.vin,r.item_name]))} for r in frappe.get_list(
		"Vehicle Master", fields=["name","vin","item_name"],
		filters={"vehicle_import_file":vif.name,"company":vif.company,"disabled":0,"docstatus":["<",2]},
		or_filters=[["vin","like",f"%{cstr(search)[:100]}%"],["name","like",f"%{cstr(search)[:100]}%"]],
		order_by="vin asc",page_length=30)]


def get_target(vehicle_import_file, vehicle):
	target = _target(_access(vehicle_import_file), vehicle)[0]
	_document_access(target["doctype"])
	return target


def _build(vif, data, lock=False):
	target, source, reason = _target(vif, data["vehicle"], lock=lock)
	if reason: frappe.throw(_(reason))
	_document_access(target["doctype"])
	account = frappe.get_doc("Account", data["expense_account"])
	account.check_permission("read")
	# Match the existing portal's selectable expense-account configuration;
	# the native LCV controller also applies its charge-account/dimension rules.
	if account.company != vif.company or account.disabled or account.is_group or account.root_type != "Expense" or account.account_type == "Stock":
		frappe.throw(_("Select an enabled landed cost expense account for this company."))
	if target["doctype"]==REVALUATION:
		return _revaluation_document(vif,data,target,source,account)
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


def _revaluation_document(vif,data,target,source,account):
	if account.account_currency!=target["company_currency"]:
		frappe.throw(_("Serial revaluation requires an expense account in company currency."))
	doc = frappe.new_doc(REVALUATION)
	doc.company = vif.company
	amount = flt(float(data["amount"]),doc.precision("difference_amount"))
	if amount<=0: frappe.throw(_("Enter a positive cost amount."))
	doc.update({"purpose":"Stock Reconciliation","company":vif.company,"posting_date":nowdate(),
		"posting_time":nowtime(),"set_posting_time":1,"expense_account":account.name,
		"cost_center":source.cost_center or frappe.get_cached_value("Company",vif.company,"cost_center"),
		CUSTOM_FIELD:vif.name,VEHICLE:target["vehicle"],"custom_portal_truck_cost_receipt":target["purchase_receipt"],
		"custom_portal_truck_cost_receipt_item":source.name,"custom_portal_truck_cost_amount":amount,
		"custom_portal_truck_cost_description":data["description"]})
	doc.append("items",{"item_code":source.item_code,"warehouse":target["warehouse"],"qty":1,
		"valuation_rate":target["current_valuation"]+amount,"reconcile_all_serial_batch":0,"use_serial_batch_fields":0})
	doc.validate_expense_account()  # read-only native validation; no bundles/drafts on preview
	summary = {**target,"amount":amount,"currency":target["company_currency"],"company_amount":amount,
		"exchange_rate":1,"expense_account":account.name,"description":data["description"],"posting_date":doc.posting_date,
		"new_valuation":doc.items[0].valuation_rate}
	return doc,summary


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
	for doctype in (DT,REVALUATION):
		if not frappe.get_meta(doctype).has_field(TOKEN): continue
		name = frappe.db.get_value(doctype,{TOKEN:token},"name",for_update=True)
		if not name: continue
		doc = frappe.get_doc(doctype,name,for_update=True)
		doc.check_permission("read"); doc.check_permission("submit")
		if doc.get(PAYLOAD) != payload: frappe.throw(_("This cost request was already used with different data."))
		if doc.docstatus != 1: frappe.throw(_("This cost request is not submitted. Review its existing voucher before starting a new cost."))
		return {"name":doc.name,"doctype":doc.doctype,"docstatus":doc.docstatus}
	doc, summary = _build(vif,data,lock=True)
	if not confirmation or confirmation != _hash(summary): frappe.throw(_("Cost details changed. Review the confirmation again."))
	doc.set(TOKEN,token);doc.set(PAYLOAD,payload)
	frappe.db.savepoint("single_truck_cost")
	try:
		if doc.doctype==REVALUATION:
			from erpnext.stock.serial_batch_bundle import SerialBatchCreation
			bundle = SerialBatchCreation({"item_code":doc.items[0].item_code,"warehouse":doc.items[0].warehouse,
				"company":doc.company,"qty":1,"avg_rate":doc.items[0].valuation_rate,"serial_nos":[summary["vin"]],
				"posting_date":doc.posting_date,"posting_time":doc.posting_time,"voucher_type":REVALUATION,
				"type_of_transaction":"Inward","do_not_submit":True}).make_serial_and_batch_bundle()
			doc.items[0].serial_and_batch_bundle = bundle.name
		doc.insert()
		doc.submit()
		if doc.doctype==REVALUATION and abs(flt(doc.difference_amount)-summary["company_amount"])>0.01:
			frappe.throw(_("Cost details changed. Review the confirmation again."))
	except Exception:
		frappe.db.rollback(save_point="single_truck_cost")
		raise
	return {"name":doc.name,"doctype":doc.doctype,"docstatus":doc.docstatus}


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
	if _details["doctype"]!=DT: frappe.throw(_(SHARED_ROW))
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


def validate_serial_revaluation(doc, method=None):
	previous = doc.get_doc_before_save()
	if not doc.get(VEHICLE):
		if doc.get(TOKEN) or previous and previous.get(VEHICLE): frappe.throw(_("Single-truck cost audit links cannot be changed."))
		return
	vif = frappe.get_doc("Vehicle Import File",doc.get(CUSTOM_FIELD))
	vif.check_permission("read")
	target,source,reason = _target(vif,doc.get(VEHICLE))
	if reason: frappe.throw(_(reason))
	if (target["doctype"]!=REVALUATION or doc.purpose!="Stock Reconciliation" or doc.company!=vif.company
		or doc.get("custom_portal_truck_cost_receipt")!=source.parent
		or doc.get("custom_portal_truck_cost_receipt_item")!=source.name or len(doc.items)!=1):
		frappe.throw(_("Serial revaluation must affect only the selected on-hand VIN."))
	row = doc.items[0]
	if (row.item_code!=source.item_code or row.warehouse!=target["warehouse"] or flt(row.qty)!=1
		or flt(row.current_qty)!=1 or row.reconcile_all_serial_batch or row.use_serial_batch_fields):
		frappe.throw(_("Serial revaluation must affect only the selected on-hand VIN."))
	for field,qty in (("serial_and_batch_bundle",1),("current_serial_and_batch_bundle",-1)):
		bundle = frappe.get_doc("Serial and Batch Bundle",row.get(field))
		if (len(bundle.entries)!=1 or bundle.entries[0].serial_no!=target["vin"]
			or flt(bundle.entries[0].qty)!=qty or bundle.warehouse!=row.warehouse or bundle.item_code!=row.item_code):
			frappe.throw(_("Serial revaluation must affect only the selected on-hand VIN."))
	if flt(doc.get("custom_portal_truck_cost_amount"))<=0 or abs(flt(doc.difference_amount)-flt(doc.get("custom_portal_truck_cost_amount")))>0.01:
		frappe.throw(_("Cost details changed. Review the confirmation again."))
	if previous and any(previous.get(f)!=doc.get(f) for f in (VEHICLE,TOKEN,PAYLOAD,CUSTOM_FIELD,
		"custom_portal_truck_cost_receipt","custom_portal_truck_cost_receipt_item","custom_portal_truck_cost_amount")):
		frappe.throw(_("Single-truck cost audit links cannot be changed."))


def validate_revaluation_cancel(doc, method=None):
	if not doc.get(VEHICLE): return
	if frappe.db.exists(REVALUATION,{VEHICLE:doc.get(VEHICLE),"docstatus":1,"creation":[">",doc.creation]}):
		frappe.throw(_("Cancel later serial revaluations for this VIN first."))


def get_revaluation(name):
	from an_truck_portal.access import require_read
	require_read(REVALUATION)
	doc = frappe.get_doc(REVALUATION,name)
	doc.check_permission("read")
	if not doc.get(VEHICLE): frappe.throw(_("Not permitted"),frappe.PermissionError)
	frappe.get_doc("Vehicle Import File",doc.get(CUSTOM_FIELD)).check_permission("read")
	vm = frappe.get_doc("Vehicle Master",doc.get(VEHICLE))
	vm.check_permission("read")
	row = doc.items[0]
	return {"name":doc.name,"doctype":doc.doctype,"company":doc.company,
		"currency":frappe.get_cached_value("Company",doc.company,"default_currency"),"docstatus":doc.docstatus,
		"posting_date":doc.posting_date,"vehicle":vm.name,"vin":vm.vin,"vehicle_import_file":doc.get(CUSTOM_FIELD),
		"purchase_receipt":doc.get("custom_portal_truck_cost_receipt"),"warehouse":row.warehouse,
		"expense_account":doc.expense_account,"description":doc.get("custom_portal_truck_cost_description"),
		"requested_amount":doc.get("custom_portal_truck_cost_amount"),"amount":doc.difference_amount,
		"previous_valuation":row.current_valuation_rate,"new_valuation":row.valuation_rate,"quantity":row.qty}
