import json
import frappe
from urllib.parse import quote

from an_truck_portal.access import require_read

ALLOWED = {
	"Vehicle Import File": ["name","import_title","company","supplier","status","country_of_origin","contract_number","contract_date","supplier_currency","total_contract_amount","expected_arrival_date","port_of_destination","total_expected_vehicles","total_received_vehicles","total_remaining_vehicles","modified"],
	"Vehicle Master": ["name","vin","chassis_number","company","item_code","item_name","vehicle_status","brand","model","model_year","color","vehicle_import_file","supplier","purchase_receipt","warehouse","customer","sales_order","sales_invoice","modified"],
	"Purchase Order": ["name","company","supplier","transaction_date","currency","grand_total","status","docstatus","modified"],
	"Purchase Receipt": ["name","company","supplier","posting_date","currency","grand_total","status","docstatus","modified"],
	"Purchase Invoice": ["name","company","supplier","posting_date","currency","grand_total","outstanding_amount","status","docstatus","modified"],
	"Supplier": ["name","supplier_name","supplier_group","country","disabled","modified"],
	"Customer": ["name","customer_name","customer_group","territory","disabled","modified"],
	"Quotation": ["name","company","party_name","customer_name","transaction_date","currency","grand_total","status","docstatus","modified"],
	"Sales Order": ["name","company","customer","customer_name","transaction_date","currency","grand_total","status","docstatus","modified"],
	"Sales Invoice": ["name","company","customer","customer_name","posting_date","currency","grand_total","outstanding_amount","status","docstatus","modified"],
	"Payment Entry": ["name","company","payment_type","party_type","party","posting_date","paid_amount","received_amount","status","docstatus","modified"],
	"Landed Cost Voucher": ["name","company","posting_date","total_taxes_and_charges","docstatus","modified"],
	"Serial No": ["name","item_code","warehouse","status","modified"],
	"Quality Inspection": ["name","inspection_type","reference_type","reference_name","item_code","sample_size","status","docstatus","modified"],
}


@frappe.whitelist()
def list_records(doctype, search=None, company=None, page=1, page_length=20, filters=None):
	if doctype not in ALLOWED: frappe.throw("Unsupported resource", frappe.ValidationError)
	require_read(doctype)
	meta = frappe.get_meta(doctype); fs = json.loads(filters) if isinstance(filters, str) and filters else (filters or {})
	if company and meta.has_field("company"): fs["company"] = company
	or_filters = None
	if search:
		search_fields = [f for f in ("name", "import_title", "vin", "supplier_name", "customer_name") if f == "name" or meta.has_field(f)]
		or_filters = [[doctype, f, "like", f"%{search}%"] for f in search_fields]
	return {"rows": frappe.get_list(doctype, filters=fs, or_filters=or_filters, fields=ALLOWED[doctype], order_by="modified desc", start=(int(page)-1)*int(page_length), page_length=min(int(page_length),100)), "page": int(page)}


@frappe.whitelist()
def get_record(doctype, name):
	if doctype not in ALLOWED: frappe.throw("Unsupported resource", frappe.ValidationError)
	require_read(doctype); doc = frappe.get_doc(doctype, name); doc.check_permission("read")
	return {"record": {f: doc.get(f) for f in ALLOWED[doctype]}, "desk_url": f"/app/{frappe.scrub(doctype).replace('_','-')}/{quote(name)}"}
