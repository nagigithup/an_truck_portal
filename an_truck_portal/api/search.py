import frappe
from an_truck_portal.access import require_access

@frappe.whitelist()
def search(q):
	require_access(); q=(q or "").strip()
	if len(q)<2: return []
	result=[]
	for dt, fields in (("Vehicle Import File",["name","import_title"]),("Vehicle Master",["name","vin","item_name"]),("Supplier",["name","supplier_name"]),("Customer",["name","customer_name"]),("Purchase Order",["name"]),("Purchase Receipt",["name"]),("Sales Order",["name"]),("Sales Invoice",["name"])):
		if frappe.db.exists("DocType",dt) and frappe.has_permission(dt,"read"):
			meta=frappe.get_meta(dt); sf=[f for f in fields if f=="name" or meta.has_field(f)]
			for row in frappe.get_list(dt,or_filters=[[dt,f,"like",f"%{q}%"] for f in sf],fields=sf,limit=5): result.append({"doctype":dt,"name":row.name,"label":next((row.get(f) for f in sf[1:] if row.get(f)),row.name)})
	return result[:20]
