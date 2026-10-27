from hashlib import sha256

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime

from an_truck_portal.api.spare_parts import SPARE_PARTS_ITEM_GROUP
from an_truck_portal.api.spare_parts_pricing import _generic_price, pricing_configuration

CENTER_TYPES = {"Warranty Provider", "Warranty Provider Branch"}


class CenterSalesReport(Document):
	def validate(self):
		self._validate_center()
		self._validate_item()
		self.report_key = sha256(
			"|".join(
				(
					self.center_type,
					self.center,
					self.company,
					self.warehouse,
					str(self.sale_date),
					self.item_code,
				)
			).encode()
		).hexdigest()
		self._validate_duplicate()
		if self.docstatus == 0 and not self.sales_invoice:
			self._capture_prices()
		if self.sales_invoice and self.docstatus == 0:
			frappe.throw(_("An invoiced center sales report cannot return to Draft."), frappe.ValidationError)

	def before_submit(self):
		if self.sales_invoice:
			frappe.throw(_("This center sales report is already invoiced."), frappe.ValidationError)
		if not frappe.has_permission("Sales Invoice", "create") or not frappe.has_permission(
			"Sales Invoice", "submit"
		):
			frappe.throw(
				_("You need permission to create and submit Sales Invoices."),
				frappe.PermissionError,
			)

	def on_submit(self):
		invoice = self._create_invoice()
		self.db_set(
			{
				"sales_invoice": invoice.name,
				"sales_invoice_item": invoice.items[0].name,
				"finalized_by": frappe.session.user,
				"finalized_on": now_datetime(),
			},
			update_modified=False,
		)

	def before_cancel(self):
		if self.sales_invoice:
			frappe.throw(
				_("Cancel the linked Sales Invoice through an approved correction workflow first."),
				frappe.ValidationError,
			)

	def _validate_center(self):
		if self.center_type not in CENTER_TYPES:
			frappe.throw(_("Select an authorized warranty provider or branch."), frappe.ValidationError)
		center = frappe.get_doc(self.center_type, self.center)
		center.check_permission("read")
		if not center.get("active") or (
			self.center_type == "Warranty Provider" and center.status != "Active"
		):
			frappe.throw(_("Select an active authorized center."), frappe.ValidationError)
		if not center.get("custom_sales_customer"):
			frappe.throw(_("Link a Sales Customer to this authorized center first."), frappe.ValidationError)
		if not center.get("custom_company_parts_warehouse"):
			frappe.throw(_("Create the center warehouse before reporting sales."), frappe.ValidationError)
		warehouse = frappe.get_doc("Warehouse", center.custom_company_parts_warehouse)
		warehouse.check_permission("read")
		if warehouse.company != self.company or warehouse.is_group or warehouse.disabled:
			frappe.throw(_("Select the active center warehouse for this company."), frappe.ValidationError)
		self.customer = center.custom_sales_customer
		self.warehouse = center.custom_company_parts_warehouse

	def _validate_item(self):
		if not self.sale_date:
			frappe.throw(_("Sale Date is required."), frappe.MandatoryError)
		if getdate(self.sale_date) > getdate():
			frappe.throw(_("Sale Date cannot be in the future."), frappe.ValidationError)
		item = frappe.get_doc("Item", self.item_code)
		item.check_permission("read")
		if item.item_group != SPARE_PARTS_ITEM_GROUP or item.disabled or not item.is_sales_item:
			frappe.throw(_("Select an enabled truck spare-parts sales item."), frappe.ValidationError)
		if flt(self.quantity) <= 0:
			frappe.throw(_("Quantity must be greater than zero."), frappe.ValidationError)
		self.stock_uom = item.stock_uom

	def _validate_duplicate(self):
		filters = {
			"center_type": self.center_type,
			"center": self.center,
			"company": self.company,
			"warehouse": self.warehouse,
			"sale_date": self.sale_date,
			"item_code": self.item_code,
			"docstatus": ["<", 2],
			"name": ["!=", self.name or ""],
		}
		if existing := frappe.db.get_value("Center Sales Report", filters, "name"):
			frappe.throw(
				_("A center sales report already exists for this center, item, and sale date: {0}.").format(
					existing
				),
				frappe.DuplicateEntryError,
			)

	def _capture_prices(self):
		config = pricing_configuration()
		retail = _generic_price(self.item_code, config.retail, self.stock_uom, self.sale_date)
		supply = _generic_price(self.item_code, config.supply, self.stock_uom, self.sale_date)
		if not retail or not flt(retail.price_list_rate):
			frappe.throw(
				_("No {0} price is configured for item {1} on {2}.").format(
					config.retail, self.item_code, self.sale_date
				),
				frappe.ValidationError,
			)
		if not supply or not flt(supply.price_list_rate):
			frappe.throw(
				_("No {0} price is configured for item {1} on {2}.").format(
					config.supply, self.item_code, self.sale_date
				),
				frappe.ValidationError,
			)
		self.retail_price_list = config.retail
		self.supply_price_list = config.supply
		self.currency = frappe.get_cached_value("Price List", config.supply, "currency")
		self.retail_price = flt(retail.price_list_rate)
		self.supply_price = flt(supply.price_list_rate)
		if self.supply_price >= self.retail_price:
			frappe.throw(_("Supply Price must be below Retail Price."), frappe.ValidationError)
		self.center_margin = self.retail_price - self.supply_price
		self.supply_amount = self.supply_price * flt(self.quantity)
		self.retail_amount = self.retail_price * flt(self.quantity)
		self.center_margin_amount = self.center_margin * flt(self.quantity)

	def _create_invoice(self):
		invoice = frappe.new_doc("Sales Invoice")
		invoice.customer = self.customer
		invoice.company = self.company
		invoice.posting_date = self.sale_date
		invoice.update_stock = 1
		invoice.set_warehouse = self.warehouse
		invoice.selling_price_list = self.supply_price_list
		invoice.currency = self.currency
		invoice.remarks = _("Center reported sale {0}").format(self.name)
		if self.notes:
			invoice.remarks += f"\n{self.notes}"
		invoice.append(
			"items",
			{
				"item_code": self.item_code,
				"qty": self.quantity,
				"warehouse": self.warehouse,
				"custom_center_sales_report": self.name,
			},
		)
		invoice.run_method("set_missing_values")
		row = invoice.items[0]
		row.price_list_rate = self.supply_price
		row.rate = self.supply_price
		invoice.run_method("calculate_taxes_and_totals")
		invoice.insert()
		invoice.submit()
		return invoice
