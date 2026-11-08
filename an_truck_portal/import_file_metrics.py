"""Read-only import commitments and standard Payment Ledger allocations.

Amounts use stored transaction/accounting values, never today's exchange rate.
Ambiguous legacy associations are unavailable rather than proportionally guessed.
"""
from collections import defaultdict
from decimal import Decimal

import frappe
from frappe.model import get_permitted_fields

LINK = "custom_vehicle_import_file"
COLUMNS = {
	"name":"Name", "supplier":"Supplier", "received_vehicles":"Received Vehicles",
	"sold_vehicles":"Sold Vehicles", "remaining_vehicles":"Remaining Vehicles",
	"purchase_value_invoice_currency":"Purchase Value (Invoice Currency)",
	"paid_amount_invoice_currency":"Paid Amount (Invoice Currency)",
	"outstanding_amount_invoice_currency":"Outstanding Amount (Invoice Currency)",
	"status":"Status", "country_of_origin":"Country of Origin", "supplier_currency":"Supplier Currency",
	"purchase_value_sar":"Purchase Value (SAR)", "paid_amount_sar":"Paid Amount (SAR)",
	"outstanding_amount_sar":"Outstanding Amount (SAR)",
}
MONEY_COLUMNS = {key for key in COLUMNS if key.startswith(("purchase_value", "paid_amount", "outstanding_amount"))}
INVOICE_FIELDS = ["name","company",LINK,"is_return","return_against","base_grand_total","supplier","credit_to",
	"currency","grand_total","conversion_rate","party_account_currency"]


def number(value):
	return Decimal(str(value or 0))


def readable(dt, fields):
	return frappe.has_permission(dt,"read") and set(fields) <= set(get_permitted_fields(dt,permission_type="read"))


def rows(dt, fields, filters, or_filters=None, **kwargs):
	return frappe.get_list(dt,fields=fields,filters=filters,or_filters=or_filters,order_by="",page_length=0,**kwargs)


def legacy_origins(field, names, companies):
	"""Resolve shared legacy references across pages, not just visible import files."""
	origins = defaultdict(set)
	if names and readable("Vehicle Master",[field,"vehicle_import_file","company"]):
		for row in rows("Vehicle Master",[field,"vehicle_import_file","company"],
			{field:["in",list(names)],"company":["in",companies],"vehicle_import_file":["is","set"]},
			group_by=", ".join([field,"vehicle_import_file","company"])):
			origins[row[field]].add(row.vehicle_import_file)
	return origins


def vehicle_counts(files, vehicles):
	"""Count receipt-backed VINs and submitted sales, excluding actual VIN returns.

	Do not call recalculate_vehicle_sales_status: that operational helper writes.
	State labels, expected quantities and receipt dates are not transaction evidence.
	"""
	companies = list({r.company for r in files.values()})
	received, sold = defaultdict(set),defaultdict(set)
	receipt_names = {v.purchase_receipt for v in vehicles if v.purchase_receipt}
	if not receipt_names:
		return received,sold,""
	if not readable("Purchase Receipt",["name","company","docstatus","is_return"]):
		return None,None,"Vehicle receipt read permission is required."
	receipts = {r.name:r.company for r in rows("Purchase Receipt",["name","company"],
		{"name":["in",list(receipt_names)],"company":["in",companies],"docstatus":1,"is_return":0})}
	eligible = {v.name:v for v in vehicles if v.vin and v.docstatus<2 and receipts.get(v.purchase_receipt)==v.company}
	for v in eligible.values(): received[v.vehicle_import_file].add(v.vin)
	if not eligible:
		return received,sold,""
	invoice_fields = ["name","company","docstatus","is_return","return_against"]
	item_fields = ["name","custom_vehicle_master","custom_vin","qty","sales_invoice_item","delivery_note","dn_detail"]
	delivery_fields = ["name","custom_vehicle_master","custom_vin","qty","si_detail","dn_detail"]
	if not (readable("Sales Invoice",invoice_fields) and readable("Delivery Note",invoice_fields)
		and set(item_fields)<=set(get_permitted_fields("Sales Invoice Item",parenttype="Sales Invoice",permission_type="read"))
		and set(delivery_fields)<=set(get_permitted_fields("Delivery Note Item",parenttype="Delivery Note",permission_type="read"))):
		return received,None,"Sales Invoice and Delivery Note read permissions are required."
	fields = invoice_fields+[f"items.{f} as item_{f}" for f in item_fields]
	invoices = rows("Sales Invoice",fields,{"company":["in",companies],"docstatus":1,"is_return":0,
		"items.custom_vehicle_master":["in",list(eligible)]})
	sales, original_items = {},{}
	for row in invoices:
		v = eligible.get(row.item_custom_vehicle_master)
		if not v or v.company!=row.company or number(row.item_qty)<=0: continue
		key = (row.name,v.name)
		# Several item rows for one VIN/invoice still represent only one vehicle.
		sale = sales.setdefault(key,{"vehicle":v,"returned":Decimal(0),"stock_returned":Decimal(0),"deliveries":set(),"delivery_items":set()})
		original_items[row.item_name] = key
		if row.item_delivery_note: sale["deliveries"].add(row.item_delivery_note)
		if row.item_dn_detail: sale["delivery_items"].add(row.item_dn_detail)
		if v.sales_invoice==row.name and v.delivery_note: sale["deliveries"].add(v.delivery_note)
	if not sales:
		return received,sold,""
	by_vin = {v.vin:v.name for v in eligible.values()}
	def vehicle_name(row):
		return row.item_custom_vehicle_master or by_vin.get(row.item_custom_vin)
	parents = list({key[0] for key in sales})
	returns = rows("Sales Invoice",fields,{"company":["in",companies],"docstatus":1,"is_return":1},
		[["Sales Invoice","return_against","in",parents],
		 ["Sales Invoice","items.sales_invoice_item","in",list(original_items)]])
	seen = set()
	for row in returns:
		if row.item_name in seen or number(row.item_qty)>=0: continue
		seen.add(row.item_name)
		key = original_items.get(row.item_sales_invoice_item) or (row.return_against,vehicle_name(row))
		if key in sales and sales[key]["vehicle"].company==row.company:
			sales[key]["returned"] -= number(row.item_qty)
	# Stock returns may precede the credit note. Resolve only explicit original
	# invoice-item, delivery-item or delivery/vehicle links; never mark every item
	# of a partly returned invoice as returned, or remove a later resale.
	deliveries, delivery_items = defaultdict(set),defaultdict(set)
	for key,sale in sales.items():
		for name in sale["deliveries"]: deliveries[name].add(key)
		for name in sale["delivery_items"]: delivery_items[name].add(key)
	return_fields = invoice_fields+[f"items.{f} as item_{f}" for f in delivery_fields]
	ors = [["Delivery Note","items.si_detail","in",list(original_items)]]
	if deliveries: ors.append(["Delivery Note","return_against","in",list(deliveries)])
	if delivery_items: ors.append(["Delivery Note","items.dn_detail","in",list(delivery_items)])
	seen = set()
	for row in rows("Delivery Note",return_fields,{"company":["in",companies],"docstatus":1,"is_return":1},ors):
		if row.item_name in seen or number(row.item_qty)>=0: continue
		seen.add(row.item_name)
		keys = ({original_items[row.item_si_detail]} if row.item_si_detail in original_items else
			delivery_items.get(row.item_dn_detail,set()) or
			{key for key in deliveries.get(row.return_against,set()) if key[1]==vehicle_name(row)})
		for key in keys:
			if sales[key]["vehicle"].company==row.company:
				sales[key]["stock_returned"] -= number(row.item_qty)
	for sale in sales.values():
		if max(sale["returned"],sale["stock_returned"])<1:
			v = sale["vehicle"]
			sold[v.vehicle_import_file].add(v.vin)
	return received,sold,""


def enrich(records):
	if not records:
		return
	files = {r.name:r for r in records}
	names = list(files)
	companies = list({r.company for r in records})
	counts, legacy_po, legacy_pr = defaultdict(int),defaultdict(set),defaultdict(set)
	vm_fields = ["name","vin","docstatus","vehicle_import_file","company","purchase_order","purchase_receipt","sales_invoice","delivery_note"]
	can_count = readable("Vehicle Master",["name",*vm_fields])
	vehicles = []
	if can_count:
		for r in rows("Vehicle Master",vm_fields,{"vehicle_import_file":["in",names],"company":["in",companies]}):
			if files[r.vehicle_import_file].company != r.company:
				continue
			vehicles.append(r)
			counts[r.vehicle_import_file] += 1
			if r.purchase_order: legacy_po[r.purchase_order].add(r.vehicle_import_file)
			if r.purchase_receipt: legacy_pr[r.purchase_receipt].add(r.vehicle_import_file)
	received,sold,vehicle_issue = vehicle_counts(files,vehicles) if can_count else (None,None,"Vehicle receipt read permission is required.")
	po_fields = ["name","company",LINK,"base_grand_total"]
	can_purchase = readable("Purchase Order",po_fields)
	orders, targets, purchase, issues = {},{},defaultdict(Decimal),{}
	if can_purchase:
		ors = [["Purchase Order",LINK,"in",names]]
		if legacy_po: ors.append(["Purchase Order","name","in",list(legacy_po)])
		for order in rows("Purchase Order",po_fields,{"company":["in",companies],"docstatus":["<",2]},ors):
			orders[order.name] = order
		legacy_po = legacy_origins("purchase_order",[o.name for o in orders.values() if not o[LINK]],companies)
		for order in orders.values():
			linked = {order[LINK]} if order[LINK] else legacy_po[order.name]
			visible = {n for n in linked if n in files and files[n].company==order.company}
			targets[order.name] = linked
			if len(linked)>1:
				for n in visible: issues[n]="Shared documents require an explicit import-file link."
			elif visible:
				purchase[next(iter(visible))] += number(order.base_grand_total)
	paid, outstanding = defaultdict(Decimal),dict(purchase)
	can_finance = can_purchase and readable("Purchase Invoice",INVOICE_FIELDS) and readable("Payment Ledger Entry",
		["name","company","account_type","party_type","party","account","voucher_type","voucher_no","against_voucher_type","against_voucher_no","amount","account_currency","amount_in_account_currency","delinked"])
	purchase_issues = dict(issues)
	invoice_issues, invoice_totals, sar_issues = {},{},{}
	if can_finance:
		invoice_totals,sar_issues = _finance(files,companies,orders,targets,legacy_pr,paid,outstanding,invoice_issues)
		issues.update(invoice_issues)
	for r in records:
		currency = r.get("company_currency")
		issue = issues.get(r.name)
		if not currency:
			issue = "Company currency is missing."
		r["vehicle_count"] = counts[r.name] if can_count else None
		r["received_vehicles"] = len(received[r.name]) if received is not None else None
		r["sold_vehicles"] = len(sold[r.name]) if sold is not None else None
		r["remaining_vehicles"] = r.received_vehicles-r.sold_vehicles if received is not None and sold is not None else None
		r["_vehicle_issue"] = vehicle_issue
		for field,values,allowed in (("purchase_value",purchase,can_purchase),("paid_amount",paid,can_finance),("outstanding_amount",outstanding,can_finance)):
			blocked = purchase_issues.get(r.name) if field=="purchase_value" else issue
			r[field] = [{"currency":currency,"amount":float(values.get(r.name,0))}] if allowed and currency and not blocked else None
		r["_finance_issue"] = issue or ("Accounting read permission is required." if not can_finance else "")
		groups = invoice_totals.get(r.name,{})
		invoice_issue = invoice_issues.get(r.name) or ("No submitted purchase invoices are linked." if not groups else "")
		if not can_finance: invoice_issue = "Accounting read permission is required."
		for field in ("purchase_value","paid_amount","outstanding_amount"):
			r[field+"_invoice_currency"] = [{"currency":cur,"amount":float(values[field])} for cur,values in sorted(groups.items())] if not invoice_issue else None
			r[field+"_sar"] = [{"currency":"SAR","amount":float(sum((values[field+"_sar"] for values in groups.values()),Decimal(0)))}] if not invoice_issue and not sar_issues.get(r.name) else None
		r["_invoice_finance_issue"] = invoice_issue
		r["_sar_finance_issue"] = invoice_issue or sar_issues.get(r.name,"")


def _finance(files,companies,orders,targets,legacy_pr,paid,outstanding,issues):
	names = list(files)
	receipts = {}
	if readable("Purchase Receipt",["name","company",LINK]):
		ors = [["Purchase Receipt",LINK,"in",names]]
		if legacy_pr: ors.append(["Purchase Receipt","name","in",list(legacy_pr)])
		for r in rows("Purchase Receipt",["name","company",LINK],{"company":["in",companies],"docstatus":["<",2]},ors):
			receipts[r.name] = {r[LINK]} if r[LINK] else set()
		origins = legacy_origins("purchase_receipt",[key for key,value in receipts.items() if not value],companies)
		for key,value in origins.items(): receipts[key] = value
	fields = INVOICE_FIELDS
	ors = [["Purchase Invoice",LINK,"in",names]]
	if orders: ors.append(["Purchase Invoice","items.purchase_order","in",list(orders)])
	if receipts: ors.append(["Purchase Invoice","items.purchase_receipt","in",list(receipts)])
	invoices = {r.name:r for r in rows("Purchase Invoice",fields,{"company":["in",companies],"docstatus":1},ors,distinct=True)}
	if invoices:
		for r in rows("Purchase Invoice",fields,{"company":["in",companies],"docstatus":1,"return_against":["in",list(invoices)]}):
			invoices[r.name] = r
	if not invoices:
		return {},{}
	unassigned = [r.name for r in invoices.values() if not r[LINK] and not r.return_against]
	item_links = defaultdict(list)
	if unassigned:
		for r in rows("Purchase Invoice",["name","items.purchase_order as purchase_order","items.purchase_receipt as purchase_receipt"],{"name":["in",unassigned]}):
			item_links[r.name].append((r.purchase_order,r.purchase_receipt))
		unknown_po = {po for links in item_links.values() for po,pr in links if po and po not in targets}
		unknown_pr = {pr for links in item_links.values() for po,pr in links if pr and pr not in receipts}
		if unknown_po:
			for r in rows("Purchase Order",["name",LINK],{"name":["in",list(unknown_po)]}):
				targets[r.name] = {r[LINK]} if r[LINK] else set()
		if unknown_pr and readable("Purchase Receipt",["name",LINK]):
			for r in rows("Purchase Receipt",["name",LINK],{"name":["in",list(unknown_pr)]}):
				receipts[r.name] = {r[LINK]} if r[LINK] else set()
	assignments = {}
	for invoice in invoices.values():
		if invoice[LINK]: assignments[invoice.name] = {invoice[LINK]}
		elif not invoice.return_against:
			linked, unresolved = set(),False
			for po,pr in item_links[invoice.name]:
				origin = targets.get(po) if po else receipts.get(pr) if pr else None
				if not origin: unresolved=True
				linked.update(origin or [])
			assignments[invoice.name] = linked
			if unresolved or len(linked)!=1:
				for n in linked & files.keys(): issues[n]="Shared documents require an explicit import-file link."
	for invoice in invoices.values():
		if invoice.return_against and not invoice[LINK]:
			assignments[invoice.name] = assignments.get(invoice.return_against,set())
	valid = {key:next(iter(linked)) for key,linked in assignments.items() if len(linked)==1 and next(iter(linked)) in files
		and invoices[key].company==files[next(iter(linked))].company}
	if not valid:
		return {},{}
	ledger = rows("Payment Ledger Entry",["name","company","party","account","voucher_type","voucher_no","against_voucher_no","amount","account_currency","amount_in_account_currency"],
		{"company":["in",companies],"account_type":"Payable","party_type":"Supplier","delinked":0,
		 "against_voucher_type":"Purchase Invoice","against_voucher_no":["in",list(valid)]})
	pe_names = {r.voucher_no for r in ledger if r.voucher_type=="Payment Entry"}
	je_names = {r.voucher_no for r in ledger if r.voucher_type=="Journal Entry"}
	payments = _read_vouchers("Payment Entry",pe_names)
	journals = _read_vouchers("Journal Entry",je_names)
	bank_journals = set()
	unknown_journals = set(journals)
	if journals and 'account' in get_permitted_fields('Journal Entry Account',parenttype='Journal Entry',permission_type='read'):
		accounts = rows("Journal Entry",["name","accounts.account as account"],{"name":["in",list(journals)]})
		if readable("Account",["name","account_type"]):
			bank = {r.name for r in rows("Account",["name"],{"name":["in",list({r.account for r in accounts})],"account_type":["in",["Bank","Cash"]]})}
			bank_journals = {r.name for r in accounts if r.account in bank}
			unknown_journals = set()
	seen, posted_invoices, accounting_rows = set(),set(),[]
	for entry in ledger:
		invoice = invoices[entry.against_voucher_no]
		name = valid[entry.against_voucher_no]
		if entry.name in seen or entry.company!=invoice.company or entry.party!=invoice.supplier or entry.account!=invoice.credit_to:
			continue
		seen.add(entry.name)
		is_payment = False
		if entry.voucher_type=="Purchase Invoice" and entry.voucher_no==invoice.name:
			posted_invoices.add(invoice.name)
		outstanding[name] = outstanding.get(name,Decimal(0)) + number(entry.amount)
		if entry.voucher_type=="Payment Entry":
			if payments.get(entry.voucher_no)!=invoice.company: issues[name]="Allocated payment documents are not readable or submitted."
			else:
				paid[name] -= number(entry.amount)
				is_payment = True
		elif entry.voucher_type=="Journal Entry":
			if journals.get(entry.voucher_no)!=invoice.company: issues[name]="Allocated payment documents are not readable or submitted."
			elif entry.voucher_no in unknown_journals: issues[name]="Accounting read permission is required."
			elif entry.voucher_no in bank_journals:
				paid[name] -= number(entry.amount)
				is_payment = True
		accounting_rows.append((entry,is_payment))
	for key,name in valid.items():
		if not invoices[key].is_return:
			outstanding[name] = outstanding.get(name,Decimal(0)) - number(invoices[key].base_grand_total)
		if not invoices[key].is_return and number(invoices[key].base_grand_total) and key not in posted_invoices:
			issues[name]="The invoice accounting ledger is incomplete."
	return _invoice_currency_totals(files,invoices,valid,accounting_rows,issues)


def _invoice_currency_totals(files,invoices,valid,ledger,issues):
	"""Net invoiced purchase amounts and active allocations in two explicit views.

	PLE account amounts are already in invoice currency for foreign payable accounts.
	For company-currency payables, use the invoice's stored conversion_rate. No
	current rate, supplier-currency guess or proportional payment split is used.
	"""
	totals = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
	sar_issues = {}
	for key,name in valid.items():
		invoice = invoices[key]
		if not invoice.currency:
			issues[name] = "Invoice currency is missing."
			continue
		values = totals[name][invoice.currency]
		values["purchase_value"] += number(invoice.grand_total)
		if files[name].company_currency=="SAR":
			if number(invoice.grand_total) and (not number(invoice.base_grand_total) or number(invoice.conversion_rate)<=0):
				sar_issues[name] = "No recorded SAR conversion is available."
			else:
				values["purchase_value_sar"] += number(invoice.base_grand_total)
		elif invoice.currency=="SAR":
			values["purchase_value_sar"] += number(invoice.grand_total)
		else:
			sar_issues[name] = "No recorded SAR conversion is available."
	for entry,is_payment in ledger:
		invoice = invoices[entry.against_voucher_no]
		name = valid[invoice.name]
		if not invoice.currency: continue
		values = totals[name][invoice.currency]
		if entry.account_currency==invoice.currency:
			amount = number(entry.amount_in_account_currency)
		elif entry.account_currency==files[name].company_currency and number(invoice.conversion_rate)>0:
			amount = number(entry.amount_in_account_currency)/number(invoice.conversion_rate)
		else:
			issues[name] = "The recorded invoice or account conversion is unavailable."
			continue
		values["outstanding_amount"] += amount
		if is_payment: values["paid_amount"] -= amount
		if files[name].company_currency=="SAR":
			sar_amount = number(entry.amount)
		elif invoice.currency=="SAR":
			sar_amount = amount
		else:
			continue
		values["outstanding_amount_sar"] += sar_amount
		if is_payment: values["paid_amount_sar"] -= sar_amount
	return totals,sar_issues


def _read_vouchers(dt,names):
	if not names or not readable(dt,["name","company","docstatus"]):
		return {}
	return {r.name:r.company for r in rows(dt,["name","company"],{"name":["in",list(names)],"docstatus":1})}
