import frappe
from an_truck import transactions
from an_truck.services import CUSTOM_FIELD
from frappe import _
from frappe.handler import upload_file
from frappe.utils import flt, nowdate

from an_truck_portal.access import require_access


def _require_mutable_import_file(name, permtype="read"):
	require_access()
	vif = frappe.get_doc("Vehicle Import File", name, for_update=True)
	vif.check_permission(permtype)
	if vif.status == "Completed":
		frappe.throw(
			_("This Vehicle Import File is completed and is read-only in AN Truck Portal."),
			frappe.PermissionError,
		)
	return vif


@frappe.whitelist(methods=["POST"])
def complete_import_file(vehicle_import_file):
	require_access()
	vif = frappe.get_doc("Vehicle Import File", vehicle_import_file, for_update=True)
	vif.check_permission("write")
	if vif.status == "Completed":
		return {"name": vif.name, "status": vif.status}
	if vif.status != "Fully Received":
		frappe.throw(_("Only a fully received Vehicle Import File can be completed."))
	vif.status = "Completed"
	vif.save()
	return {"name": vif.name, "status": vif.status}


@frappe.whitelist(methods=["POST"])
def create_purchase_order(vehicle_import_file, data=None, submit_now=0, idempotency_key=None):
	_require_mutable_import_file(vehicle_import_file)
	return transactions.create_purchase_order(vehicle_import_file, data, submit_now, idempotency_key)


@frappe.whitelist(methods=["POST"])
def create_purchase_receipt(vehicle_import_file, data=None, submit_now=0, idempotency_key=None):
	_require_mutable_import_file(vehicle_import_file)
	return transactions.create_purchase_receipt(vehicle_import_file, data, submit_now, idempotency_key)


@frappe.whitelist(methods=["POST"])
def create_purchase_invoice(vehicle_import_file, data=None, submit_now=0, idempotency_key=None):
	_require_mutable_import_file(vehicle_import_file)
	return transactions.create_purchase_invoice(vehicle_import_file, data, submit_now, idempotency_key)


@frappe.whitelist(methods=["POST"])
def create_payment_entry(vehicle_import_file, data=None, submit_now=0, idempotency_key=None):
	_require_mutable_import_file(vehicle_import_file)
	return transactions.create_payment_entry(vehicle_import_file, data, submit_now, idempotency_key)


@frappe.whitelist(methods=["POST"])
def create_landed_cost_voucher(vehicle_import_file, data=None, submit_now=0, idempotency_key=None):
	_require_mutable_import_file(vehicle_import_file)
	return transactions.create_landed_cost_voucher(vehicle_import_file, data, submit_now, idempotency_key)


@frappe.whitelist(methods=["POST"])
def upload_cost_attachment(vehicle_import_file):
	_require_mutable_import_file(vehicle_import_file)
	if frappe.form_dict.doctype != "Landed Cost Taxes and Charges":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	parent = frappe.db.get_value(
		"Landed Cost Taxes and Charges",
		frappe.form_dict.docname,
		"parent",
	)
	linked_import_file = frappe.db.get_value("Landed Cost Voucher", parent, CUSTOM_FIELD) if parent else None
	if linked_import_file != vehicle_import_file:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return upload_file()


@frappe.whitelist(methods=["POST"])
def upload_purchase_order_attachment(vehicle_import_file):
	_require_mutable_import_file(vehicle_import_file)
	if frappe.form_dict.doctype != "Purchase Order":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	linked_import_file = frappe.db.get_value("Purchase Order", frappe.form_dict.docname, CUSTOM_FIELD)
	if linked_import_file != vehicle_import_file:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return upload_file()


@frappe.whitelist(methods=["POST"])
def upload_purchase_invoice_attachment(vehicle_import_file):
	_require_mutable_import_file(vehicle_import_file)
	if frappe.form_dict.doctype != "Purchase Invoice":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	linked_import_file = frappe.db.get_value("Purchase Invoice", frappe.form_dict.docname, CUSTOM_FIELD)
	if linked_import_file != vehicle_import_file:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return upload_file()


@frappe.whitelist(methods=["POST"])
def upload_supplier_payment_attachment(payment_entry, purchase_invoice):
	require_access()
	if frappe.form_dict.doctype != "Payment Entry" or frappe.form_dict.docname != payment_entry:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	payment = frappe.get_doc("Payment Entry", payment_entry)
	payment.check_permission("read")
	if payment.payment_type != "Pay" or payment.party_type != "Supplier":
		frappe.throw(_("This payment is not a supplier payment."), frappe.PermissionError)
	if not any(
		row.reference_doctype == "Purchase Invoice" and row.reference_name == purchase_invoice
		for row in payment.references
	):
		frappe.throw(_("Payment Entry is not linked to this Purchase Invoice."), frappe.PermissionError)
	invoice = frappe.get_doc("Purchase Invoice", purchase_invoice)
	invoice.check_permission("read")
	vehicle_import_file = invoice.get(CUSTOM_FIELD)
	if vehicle_import_file:
		_require_mutable_import_file(vehicle_import_file)
		if payment.get(CUSTOM_FIELD) != vehicle_import_file:
			frappe.throw(_("Not permitted"), frappe.PermissionError)
	return upload_file()


def _payment_modes(company):
	modes = []
	for mode in frappe.get_all(
		"Mode of Payment",
		filters={"enabled": 1},
		fields=["name", "type"],
		order_by="name asc",
	):
		account = frappe.db.get_value(
			"Mode of Payment Account",
			{"parent": mode.name, "company": company},
			"default_account",
		)
		if not account or not frappe.has_permission("Account", "read", account):
			continue
		modes.append(
			{
				"name": mode.name,
				"type": mode.type,
				"requires_reference": frappe.get_cached_value("Account", account, "account_type") == "Bank",
			}
		)
	return modes


@frappe.whitelist(methods=["GET"])
def get_supplier_payment_form(purchase_invoice):
	require_access()
	invoice = frappe.get_doc("Purchase Invoice", purchase_invoice)
	invoice.check_permission("read")
	if not frappe.has_permission("Payment Entry", "create"):
		frappe.throw(_("Not permitted to create Payment Entry."), frappe.PermissionError)
	if invoice.docstatus != 1 or flt(invoice.outstanding_amount) <= 0:
		frappe.throw(_("This Purchase Invoice has no outstanding balance."))
	vehicle_import_file = invoice.get(CUSTOM_FIELD)
	if vehicle_import_file:
		_require_mutable_import_file(vehicle_import_file)
	modes = _payment_modes(invoice.company)
	default_mode = invoice.get("mode_of_payment")
	if default_mode not in {mode["name"] for mode in modes}:
		default_mode = modes[0]["name"] if len(modes) == 1 else ""
	return {
		"purchase_invoice": invoice.name,
		"vehicle_import_file": vehicle_import_file,
		"supplier": invoice.supplier,
		"supplier_name": invoice.supplier_name,
		"company": invoice.company,
		"currency": invoice.currency,
		"outstanding_amount": invoice.outstanding_amount,
		"payment_date": nowdate(),
		"reference_date": nowdate(),
		"mode_of_payment": default_mode,
		"modes_of_payment": modes,
	}


@frappe.whitelist(methods=["POST"])
def record_supplier_payment(purchase_invoice, data=None, idempotency_key=None):
	from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	require_access()
	data = frappe.parse_json(data) if isinstance(data, str) else frappe._dict(data or {})
	if not idempotency_key:
		frappe.throw(_("Unable to safely process this payment. Please reopen the form and try again."))
	cache_key = f"an_truck_portal:invoice_payment:{purchase_invoice}:{idempotency_key}"
	if existing := frappe.cache().get_value(cache_key):
		return existing

	invoice = frappe.get_doc("Purchase Invoice", purchase_invoice, for_update=True)
	invoice.check_permission("read")
	if existing := frappe.cache().get_value(cache_key):
		return existing
	if invoice.docstatus != 1 or flt(invoice.outstanding_amount) <= 0:
		frappe.throw(_("This Purchase Invoice has no outstanding balance."))
	vehicle_import_file = invoice.get(CUSTOM_FIELD)
	if vehicle_import_file:
		_require_mutable_import_file(vehicle_import_file)

	amount = flt(data.get("amount"), invoice.precision("outstanding_amount"))
	if amount <= 0 or amount > flt(
		invoice.outstanding_amount,
		invoice.precision("outstanding_amount"),
	):
		frappe.throw(_("Payment amount must be greater than zero and cannot exceed the outstanding amount."))
	mode_of_payment = data.get("mode_of_payment")
	if not mode_of_payment:
		frappe.throw(_("Mode of Payment is required."))
	if not frappe.db.get_value("Mode of Payment", mode_of_payment, "enabled"):
		frappe.throw(_("Mode of Payment {0} is disabled.").format(mode_of_payment))
	bank = get_default_bank_cash_account(
		invoice.company,
		mode_of_payment=mode_of_payment,
		fetch_balance=False,
	)
	if not bank:
		frappe.throw(_("No account is configured for Mode of Payment {0}.").format(mode_of_payment))

	doc = get_payment_entry(
		"Purchase Invoice",
		invoice.name,
		party_amount=amount,
		bank_account=bank.account,
		reference_date=data.get("reference_date") or data.get("payment_date") or nowdate(),
	)
	doc.mode_of_payment = mode_of_payment
	doc.posting_date = data.get("payment_date") or nowdate()
	doc.reference_no = data.get("reference_number")
	doc.reference_date = data.get("reference_date") or doc.posting_date
	if data.get("notes"):
		doc.custom_remarks = 1
		doc.remarks = data.get("notes")
	if vehicle_import_file:
		doc.set(CUSTOM_FIELD, vehicle_import_file)
	doc.set_exchange_rate()
	doc.set_amounts()
	doc.insert()
	doc.submit()
	result = {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"status": doc.status,
	}
	frappe.cache().set_value(cache_key, result, expires_in_sec=60 * 60)
	return result


@frappe.whitelist(methods=["GET"])
def get_purchase_invoice_form(purchase_order):
	require_access()
	po = frappe.get_doc("Purchase Order", purchase_order)
	po.check_permission("read")
	if not frappe.has_permission("Purchase Invoice", "create"):
		frappe.throw(_("Not permitted to create Purchase Invoice."), frappe.PermissionError)
	if po.docstatus != 1:
		frappe.throw(_("Purchase Order must be submitted before invoicing."))
	if po.status in {"Closed", "On Hold"}:
		frappe.throw(_("This Purchase Order is not eligible for invoicing."))
	vehicle_import_file = po.get(CUSTOM_FIELD)
	if not vehicle_import_file:
		frappe.throw(_("Purchase Order is not linked to a Vehicle Import File."))
	vif = frappe.get_doc("Vehicle Import File", vehicle_import_file)
	vif.check_permission("read")
	if vif.status == "Completed":
		frappe.throw(
			_("This Vehicle Import File is completed and is read-only in AN Truck Portal."),
			frappe.PermissionError,
		)
	draft_invoice = frappe.db.get_value(
		"Purchase Invoice Item",
		{"purchase_order": po.name, "docstatus": 0},
		"parent",
	)
	if draft_invoice:
		frappe.throw(_("Draft Purchase Invoice {0} already exists for this Purchase Order.").format(draft_invoice))
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

	doc = make_purchase_invoice(po.name)
	if not doc.items:
		frappe.throw(_("All items in this Purchase Order have already been invoiced."))
	return {
		"vehicle_import_file": vehicle_import_file,
		"purchase_order": po.name,
		"supplier": doc.supplier,
		"supplier_name": doc.supplier_name,
		"company": doc.company,
		"currency": doc.currency,
		"posting_date": nowdate(),
		"due_date": doc.due_date,
		"items": [
			{
				"source_item": row.po_detail,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"description": row.description,
				"qty": row.qty,
				"max_qty": row.qty,
				"uom": row.uom,
				"rate": row.rate,
				"amount": row.amount,
			}
			for row in doc.items
		],
	}


@frappe.whitelist(methods=["GET"])
def get_purchase_order(purchase_order):
	require_access()
	doc = frappe.get_doc("Purchase Order", purchase_order)
	doc.check_permission("read")
	attachments = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Purchase Order", "attached_to_name": doc.name, "is_folder": 0},
		fields=["name", "file_name", "file_url", "is_private"],
		order_by="creation asc",
	)
	linked_documents = []
	for doctype, child_doctype, date_field in (
		("Purchase Receipt", "Purchase Receipt Item", "posting_date"),
		("Purchase Invoice", "Purchase Invoice Item", "posting_date"),
	):
		if not frappe.has_permission(doctype, "read"):
			continue
		names = list(
			{
				row.parent
				for row in frappe.get_all(
					child_doctype,
					filters={"purchase_order": doc.name, "docstatus": ["<", 2]},
					fields=["parent"],
				)
			}
		)
		if names:
			for row in frappe.get_list(
				doctype,
				filters={"name": ["in", names]},
				fields=["name", f"{date_field} as date", "status", "docstatus"],
				order_by=f"{date_field} desc",
			):
				row["doctype"] = doctype
				linked_documents.append(row)
	draft_invoice = frappe.db.get_value(
		"Purchase Invoice Item",
		{"purchase_order": doc.name, "docstatus": 0},
		"parent",
	)
	return {
		"purchase_order": {
			"name": doc.name,
			"vehicle_import_file": doc.get(CUSTOM_FIELD),
			"supplier": doc.supplier,
			"supplier_name": doc.supplier_name,
			"company": doc.company,
			"transaction_date": doc.transaction_date,
			"schedule_date": doc.schedule_date,
			"currency": doc.currency,
			"status": doc.status,
			"docstatus": doc.docstatus,
			"per_billed": doc.per_billed,
			"total_qty": doc.total_qty,
			"net_total": doc.net_total,
			"total_taxes_and_charges": doc.total_taxes_and_charges,
			"grand_total": doc.grand_total,
			"rounded_total": doc.rounded_total,
			"remarks": doc.get("remarks"),
		},
		"items": [
			{
				"name": row.name,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"description": row.description,
				"qty": row.qty,
				"received_qty": row.received_qty,
				"billed_amt": row.get("billed_amt"),
				"uom": row.uom,
				"rate": row.rate,
				"amount": row.amount,
				"warehouse": row.warehouse,
				"schedule_date": row.schedule_date,
			}
			for row in doc.items
		],
		"attachments": attachments,
		"linked_documents": linked_documents,
		"can_create_purchase_invoice": bool(
			doc.docstatus == 1
			and doc.status not in {"Closed", "On Hold"}
			and flt(doc.per_billed) < 100
			and doc.get(CUSTOM_FIELD)
			and frappe.has_permission("Purchase Invoice", "create")
			and frappe.db.get_value("Vehicle Import File", doc.get(CUSTOM_FIELD), "status") != "Completed"
			and not draft_invoice
		),
	}


@frappe.whitelist(methods=["GET"])
def get_purchase_receipt(purchase_receipt):
	require_access()
	doc = frappe.get_doc("Purchase Receipt", purchase_receipt)
	doc.check_permission("read")
	attachments = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Purchase Receipt", "attached_to_name": doc.name, "is_folder": 0},
		fields=["name", "file_name", "file_url", "is_private"],
		order_by="creation asc",
	)
	linked_documents = []
	seen = set()
	for row in doc.items:
		purchase_order = row.get("purchase_order")
		if not purchase_order or purchase_order in seen or not frappe.has_permission(
			"Purchase Order", "read", purchase_order
		):
			continue
		seen.add(purchase_order)
		linked = frappe.db.get_value(
			"Purchase Order",
			purchase_order,
			["name", "status", "docstatus", "transaction_date as date"],
			as_dict=True,
		)
		if linked:
			linked["doctype"] = "Purchase Order"
			linked_documents.append(linked)
	if frappe.has_permission("Purchase Invoice", "read"):
		invoice_names = frappe.get_all(
			"Purchase Invoice Item",
			filters={"purchase_receipt": doc.name, "docstatus": ["<", 2]},
			pluck="parent",
		)
		if invoice_names:
			for linked in frappe.get_list(
				"Purchase Invoice",
				filters={"name": ["in", list(set(invoice_names))]},
				fields=["name", "status", "docstatus", "posting_date as date"],
			):
				linked["doctype"] = "Purchase Invoice"
				linked_documents.append(linked)
	if frappe.has_permission("Landed Cost Voucher", "read"):
		voucher_names = frappe.get_all(
			"Landed Cost Purchase Receipt",
			filters={
				"receipt_document_type": "Purchase Receipt",
				"receipt_document": doc.name,
				"docstatus": ["<", 2],
			},
			pluck="parent",
		)
		if voucher_names:
			for linked in frappe.get_list(
				"Landed Cost Voucher",
				filters={"name": ["in", list(set(voucher_names))]},
				fields=["name", "docstatus", "posting_date as date"],
			):
				linked["doctype"] = "Landed Cost Voucher"
				linked["status"] = "Submitted" if linked.docstatus == 1 else "Draft"
				linked_documents.append(linked)
	return {
		"purchase_receipt": {
			"name": doc.name,
			"vehicle_import_file": doc.get(CUSTOM_FIELD),
			"supplier": doc.get("supplier"),
			"supplier_name": doc.get("supplier_name"),
			"company": doc.get("company"),
			"posting_date": doc.get("posting_date"),
			"posting_time": doc.get("posting_time"),
			"currency": doc.get("currency"),
			"status": doc.get("status"),
			"docstatus": doc.docstatus,
			"total_qty": doc.get("total_qty"),
			"net_total": doc.get("net_total"),
			"total_taxes_and_charges": doc.get("total_taxes_and_charges"),
			"grand_total": doc.get("grand_total"),
			"rounded_total": doc.get("rounded_total"),
			"remarks": doc.get("remarks"),
		},
		"items": [
			{
				"name": row.name,
				"item_code": row.get("item_code"),
				"item_name": row.get("item_name"),
				"description": row.get("description"),
				"received_qty": row.get("received_qty"),
				"qty": row.get("qty"),
				"rejected_qty": row.get("rejected_qty"),
				"uom": row.get("uom"),
				"rate": row.get("rate"),
				"amount": row.get("amount"),
				"warehouse": row.get("warehouse"),
				"rejected_warehouse": row.get("rejected_warehouse"),
				"purchase_order": row.get("purchase_order"),
			}
			for row in doc.items
		],
		"attachments": attachments,
		"linked_documents": linked_documents,
	}


@frappe.whitelist(methods=["GET"])
def get_supplier_payment(payment_entry):
	require_access()
	doc = frappe.get_doc("Payment Entry", payment_entry)
	doc.check_permission("read")
	if doc.payment_type != "Pay" or doc.party_type != "Supplier":
		frappe.throw(_("This payment is not a supplier payment."))
	attachments = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Payment Entry", "attached_to_name": doc.name, "is_folder": 0},
		fields=["name", "file_name", "file_url", "is_private"],
		order_by="creation asc",
	)
	return {
		"payment": {
			"name": doc.name,
			"vehicle_import_file": doc.get(CUSTOM_FIELD),
			"supplier": doc.get("party"),
			"supplier_name": doc.get("party_name"),
			"company": doc.get("company"),
			"posting_date": doc.get("posting_date"),
			"payment_method": doc.get("mode_of_payment"),
			"paid_from": doc.get("paid_from"),
			"paid_to": doc.get("paid_to"),
			"paid_amount": doc.get("paid_amount"),
			"received_amount": doc.get("received_amount"),
			"paid_from_currency": doc.get("paid_from_account_currency"),
			"paid_to_currency": doc.get("paid_to_account_currency"),
			"reference_no": doc.get("reference_no"),
			"reference_date": doc.get("reference_date"),
			"status": doc.get("status"),
			"docstatus": doc.docstatus,
			"remarks": doc.get("remarks"),
		},
		"references": [
			{
				"name": row.name,
				"doctype": row.get("reference_doctype"),
				"document": row.get("reference_name"),
				"total_amount": row.get("total_amount"),
				"outstanding_amount": row.get("outstanding_amount"),
				"allocated_amount": row.get("allocated_amount"),
				"exchange_rate": row.get("exchange_rate"),
			}
			for row in doc.references
		],
		"attachments": attachments,
	}


@frappe.whitelist(methods=["GET"])
def get_landed_cost_voucher(landed_cost_voucher):
	require_access()
	doc = frappe.get_doc("Landed Cost Voucher", landed_cost_voucher)
	doc.check_permission("read")
	attachments = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Landed Cost Voucher", "attached_to_name": doc.name, "is_folder": 0},
		fields=["name", "file_name", "file_url", "is_private"],
		order_by="creation asc",
	)
	cost_row_names = [row.name for row in doc.taxes]
	cost_attachments = {name: [] for name in cost_row_names}
	if cost_row_names:
		for file in frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": "Landed Cost Taxes and Charges",
				"attached_to_name": ["in", cost_row_names],
				"is_folder": 0,
			},
			fields=["name", "file_name", "file_url", "is_private", "attached_to_name"],
			order_by="creation asc",
		):
			cost_attachments.setdefault(file.attached_to_name, []).append(file)
	purchase_receipts = []
	for row in doc.purchase_receipts:
		receipt = {
			"name": row.name,
			"doctype": row.get("receipt_document_type"),
			"document": row.get("receipt_document"),
			"supplier": row.get("supplier"),
			"posting_date": row.get("posting_date"),
			"grand_total": row.get("grand_total"),
		}
		if receipt["doctype"] == "Purchase Receipt" and frappe.has_permission(
			"Purchase Receipt", "read", doc=receipt["document"]
		):
			linked_receipt = frappe.db.get_value(
				"Purchase Receipt",
				receipt["document"],
				["supplier", "posting_date", "grand_total", "currency"],
				as_dict=True,
			)
			if linked_receipt:
				receipt.update(linked_receipt)
		purchase_receipts.append(receipt)
	return {
		"voucher": {
			"name": doc.name,
			"vehicle_import_file": doc.get(CUSTOM_FIELD),
			"company": doc.get("company"),
			"company_currency": frappe.get_cached_value("Company", doc.get("company"), "default_currency"),
			"posting_date": doc.get("posting_date"),
			"allocation_method": doc.get("distribute_charges_based_on"),
			"total_taxes_and_charges": doc.get("total_taxes_and_charges"),
			"docstatus": doc.docstatus,
			"status": "Cancelled" if doc.docstatus == 2 else "Submitted" if doc.docstatus == 1 else "Draft",
		},
		"purchase_receipts": purchase_receipts,
		"costs": [
			{
				"name": row.name,
				"description": row.get("description"),
				"expense_account": row.get("expense_account"),
				"account_currency": row.get("account_currency"),
				"amount": row.get("amount"),
				"base_amount": row.get("base_amount"),
				"exchange_rate": row.get("exchange_rate"),
				"attachments": cost_attachments.get(row.name, []),
			}
			for row in doc.taxes
		],
		"allocations": [
			{
				"name": row.name,
				"item_code": row.get("item_code"),
				"description": row.get("description"),
				"receipt_document_type": row.get("receipt_document_type"),
				"receipt_document": row.get("receipt_document"),
				"qty": row.get("qty"),
				"rate": row.get("rate"),
				"amount": row.get("amount"),
				"allocated_cost": row.get("applicable_charges"),
			}
			for row in doc.items
		],
		"attachments": attachments,
	}


@frappe.whitelist(methods=["GET"])
def get_purchase_invoice(purchase_invoice):
	require_access()
	doc = frappe.get_doc("Purchase Invoice", purchase_invoice)
	doc.check_permission("read")
	attachments = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Purchase Invoice", "attached_to_name": doc.name, "is_folder": 0},
		fields=["name", "file_name", "file_url", "is_private"],
		order_by="creation asc",
	)
	linked_documents = []
	seen = set()
	for row in doc.items:
		for doctype, name in (("Purchase Order", row.purchase_order), ("Purchase Receipt", row.purchase_receipt)):
			if not name or (doctype, name) in seen or not frappe.has_permission(doctype, "read", name):
				continue
			seen.add((doctype, name))
			linked = frappe.db.get_value(
				doctype,
				name,
				["name", "status", "docstatus", "transaction_date" if doctype == "Purchase Order" else "posting_date"],
				as_dict=True,
			)
			if linked:
				linked["doctype"] = doctype
				linked["date"] = linked.pop(
					"transaction_date" if doctype == "Purchase Order" else "posting_date"
				)
				linked_documents.append(linked)
	if frappe.has_permission("Payment Entry", "read"):
		payment_names = frappe.get_all(
			"Payment Entry Reference",
			filters={"reference_doctype": "Purchase Invoice", "reference_name": doc.name, "docstatus": ["<", 2]},
			pluck="parent",
		)
		if payment_names:
			for linked in frappe.get_list(
				"Payment Entry",
				filters={"name": ["in", list(set(payment_names))]},
				fields=["name", "status", "docstatus", "posting_date as date"],
			):
				linked["doctype"] = "Payment Entry"
				linked_documents.append(linked)
	vehicle_import_file = doc.get(CUSTOM_FIELD)
	can_record_payment = (
		doc.docstatus == 1
		and flt(doc.outstanding_amount) > 0
		and frappe.has_permission("Payment Entry", "create")
		and (
			not vehicle_import_file
			or frappe.get_cached_value("Vehicle Import File", vehicle_import_file, "status") != "Completed"
		)
	)
	return {
		"purchase_invoice": {
			"name": doc.name,
			"vehicle_import_file": vehicle_import_file,
			"supplier": doc.supplier,
			"supplier_name": doc.supplier_name,
			"company": doc.company,
			"posting_date": doc.posting_date,
			"due_date": doc.due_date,
			"bill_no": doc.bill_no,
			"bill_date": doc.bill_date,
			"currency": doc.currency,
			"status": doc.status,
			"docstatus": doc.docstatus,
			"total_qty": doc.total_qty,
			"net_total": doc.net_total,
			"total_taxes_and_charges": doc.total_taxes_and_charges,
			"grand_total": doc.grand_total,
			"rounded_total": doc.rounded_total,
			"outstanding_amount": doc.outstanding_amount,
			"paid_amount": doc.paid_amount,
			"remarks": doc.get("remarks"),
			"can_record_payment": can_record_payment,
		},
		"items": [
			{
				"name": row.name,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"description": row.description,
				"qty": row.qty,
				"uom": row.uom,
				"rate": row.rate,
				"amount": row.amount,
				"purchase_order": row.purchase_order,
				"purchase_receipt": row.purchase_receipt,
			}
			for row in doc.items
		],
		"attachments": attachments,
		"linked_documents": linked_documents,
	}


@frappe.whitelist(methods=["POST"])
def create_customer_quotation(vehicle_import_file, data=None, submit_now=0, idempotency_key=None):
	_require_mutable_import_file(vehicle_import_file)
	return transactions.create_customer_quotation(vehicle_import_file, data, submit_now, idempotency_key)


@frappe.whitelist(methods=["POST"])
def create_sales_order(vehicle_import_file, data=None, submit_now=0, idempotency_key=None):
	_require_mutable_import_file(vehicle_import_file)
	return transactions.create_sales_order(vehicle_import_file, data, submit_now, idempotency_key)


@frappe.whitelist(methods=["POST"])
def create_delivery_note(vehicle_import_file, data=None, submit_now=0, idempotency_key=None):
	_require_mutable_import_file(vehicle_import_file)
	return transactions.create_delivery_note(vehicle_import_file, data, submit_now, idempotency_key)


@frappe.whitelist(methods=["POST"])
def create_sales_invoice(vehicle_import_file, data=None, submit_now=0, idempotency_key=None):
	_require_mutable_import_file(vehicle_import_file)
	return transactions.create_sales_invoice(vehicle_import_file, data, submit_now, idempotency_key)


@frappe.whitelist(methods=["POST"])
def complete_vehicle_information(vehicle_import_file, data=None):
	_require_mutable_import_file(vehicle_import_file, "write")
	return transactions.complete_vehicle_information(vehicle_import_file, data)


@frappe.whitelist(methods=["POST"])
def start_vehicle_inspection(vehicle_import_file, data=None):
	_require_mutable_import_file(vehicle_import_file, "write")
	return transactions.start_vehicle_inspection(vehicle_import_file, data)
