"""Standard ERPNext price-list maintenance for truck spare parts."""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from an_truck_portal.access import require_access
from an_truck_portal.api.spare_parts import SPARE_PARTS_ITEM_GROUP, _accessible_warehouses

PRICE_MANAGER_ROLES = {"System Manager", "Sales Master Manager"}


def can_manage_prices():
	return bool(PRICE_MANAGER_ROLES.intersection(frappe.get_roles())) and bool(
		frappe.has_permission("Item Price", "write") or frappe.has_permission("Item Price", "create")
	)


def pricing_configuration(require_supply=True):
	retail = frappe.get_single_value("Selling Settings", "selling_price_list")
	supply = frappe.get_single_value("Selling Settings", "custom_spare_parts_supply_price_list")
	if not retail:
		frappe.throw(_("Configure the default Retail Price List in Selling Settings."), frappe.ValidationError)
	for label, value in ((_("Retail Price List"), retail), (_("Supply Price List"), supply)):
		if not value:
			if require_supply:
				frappe.throw(_("Configure the Spare Parts Supply Price List in Selling Settings."), frappe.ValidationError)
			continue
		row = frappe.db.get_value("Price List", value, ["enabled", "selling", "currency"], as_dict=True)
		if not row or not row.enabled or not row.selling:
			frappe.throw(_("{0} must be an enabled selling Price List.").format(label), frappe.ValidationError)
	if supply and supply == retail:
		frappe.throw(_("Retail and Supply Price Lists must be different."), frappe.ValidationError)
	if supply and frappe.get_cached_value("Price List", supply, "currency") != frappe.get_cached_value(
		"Price List", retail, "currency"
	):
		frappe.throw(_("Retail and Supply Price Lists must use the same currency."), frappe.ValidationError)
	return frappe._dict(retail=retail, supply=supply)


def valuation_cost(item_code, company):
	warehouses = [row.name for row in _accessible_warehouses(company)]
	if not warehouses:
		return None
	bins = frappe.get_list(
		"Bin",
		filters={"item_code": item_code, "warehouse": ["in", warehouses]},
		fields=["actual_qty", "stock_value", "valuation_rate"],
		page_length=0,
	)
	qty = sum(flt(row.actual_qty) for row in bins)
	stock_value = sum(flt(row.stock_value) for row in bins)
	if qty > 0 and stock_value > 0:
		return stock_value / qty
	rates = [flt(row.valuation_rate) for row in bins if flt(row.valuation_rate) > 0]
	return max(rates) if rates else None


def _generic_price(item_code, price_list, uom=None, on_date=None):
	if not price_list:
		return None
	filters = {
		"item_code": item_code,
		"price_list": price_list,
		"customer": ["is", "not set"],
		"supplier": ["is", "not set"],
		"batch_no": ["is", "not set"],
	}
	if uom:
		filters["uom"] = uom
	rows = frappe.get_all(
		"Item Price",
		filters=filters,
		fields=["name", "price_list_rate", "currency", "uom", "valid_from", "valid_upto"],
		order_by="valid_from desc, modified desc",
		page_length=0,
	)
	today = getdate(on_date or nowdate())
	return next(
		(
			row
			for row in rows
			if (not row.valid_from or getdate(row.valid_from) <= today)
			and (not row.valid_upto or getdate(row.valid_upto) >= today)
		),
		None,
	)


def _prices(item_code, uom, config):
	return _generic_price(item_code, config.retail, uom), _generic_price(item_code, config.supply, uom)


def _validate_values(cost, retail, supply):
	if cost is None:
		frappe.throw(_("Valuation cost is missing for this item and company; prices were not saved."), frappe.ValidationError)
	if retail is None or supply is None:
		frappe.throw(_("Enter both Retail Price and Supply Price."), frappe.ValidationError)
	if flt(supply) <= flt(cost):
		frappe.throw(_("Supply Price must be above valuation cost."), frappe.ValidationError)
	if flt(supply) >= flt(retail):
		frappe.throw(_("Supply Price must be below Retail Price."), frappe.ValidationError)


@frappe.whitelist(methods=["GET"])
def get_pricing(item_code, company):
	require_access()
	if not company:
		frappe.throw(_("Company is required."), frappe.MandatoryError)
	item = frappe.get_doc("Item", item_code)
	item.check_permission("read")
	if item.item_group != SPARE_PARTS_ITEM_GROUP:
		frappe.throw(_("Select a truck spare-parts item."), frappe.ValidationError)
	config = pricing_configuration()
	retail, supply = _prices(item.name, item.stock_uom, config)
	cost = valuation_cost(item.name, company)
	return {
		"item_code": item.name,
		"item_name": item.item_name,
		"stock_uom": item.stock_uom,
		"valuation_cost": cost,
		"cost_missing": cost is None,
		"retail_price": retail.price_list_rate if retail else None,
		"supply_price": supply.price_list_rate if supply else None,
		"retail_price_list": config.retail,
		"supply_price_list": config.supply,
		"currency": frappe.get_cached_value("Price List", config.retail, "currency"),
		"can_write": can_manage_prices(),
	}


def _save_price(item, price_list, rate):
	row = _generic_price(item.name, price_list, item.stock_uom)
	doc = frappe.get_doc("Item Price", row.name) if row else frappe.new_doc("Item Price")
	doc.check_permission("write" if row else "create")
	doc.item_code = item.name
	doc.price_list = price_list
	doc.uom = item.stock_uom
	doc.price_list_rate = flt(rate)
	doc.save()


@frappe.whitelist(methods=["POST"])
def save_pricing(item_code, company, retail_price, supply_price):
	require_access()
	if not company:
		frappe.throw(_("Company is required."), frappe.MandatoryError)
	if not can_manage_prices():
		frappe.throw(_("You are not permitted to maintain spare-parts prices."), frappe.PermissionError)
	item = frappe.get_doc("Item", item_code)
	item.check_permission("read")
	if item.item_group != SPARE_PARTS_ITEM_GROUP:
		frappe.throw(_("Select a truck spare-parts item."), frappe.ValidationError)
	config = pricing_configuration()
	cost = valuation_cost(item.name, company)
	_validate_values(cost, flt(retail_price), flt(supply_price))
	frappe.flags.spare_parts_pricing_pair_validated = True
	try:
		_save_price(item, config.retail, retail_price)
		_save_price(item, config.supply, supply_price)
	finally:
		frappe.flags.spare_parts_pricing_pair_validated = False
	return get_pricing(item.name, company)


def validate_item_price(doc, method=None):
	"""Protect portal-managed price lists even when Item Price is edited in Desk/import."""
	if frappe.flags.spare_parts_pricing_pair_validated or not doc.item_code or not doc.price_list:
		return
	if doc.customer or doc.supplier or doc.batch_no:
		return
	if frappe.get_cached_value("Item", doc.item_code, "item_group") != SPARE_PARTS_ITEM_GROUP:
		return
	config = pricing_configuration(require_supply=False)
	if doc.price_list not in {config.retail, config.supply}:
		return
	if not can_manage_prices():
		frappe.throw(_("You are not permitted to maintain spare-parts prices."), frappe.PermissionError)
	item = frappe.get_cached_doc("Item", doc.item_code)
	if doc.uom and doc.uom != item.stock_uom:
		return
	retail, supply = _prices(item.name, item.stock_uom, config)
	retail_rate = flt(doc.price_list_rate) if doc.price_list == config.retail else (retail.price_list_rate if retail else None)
	supply_rate = flt(doc.price_list_rate) if doc.price_list == config.supply else (supply.price_list_rate if supply else None)
	if supply_rate is None:
		return
	company = frappe.defaults.get_user_default("Company") or frappe.defaults.get_global_default("company")
	if not company:
		frappe.throw(_("Set a default Company before maintaining spare-parts prices."), frappe.ValidationError)
	_validate_values(valuation_cost(item.name, company), retail_rate, supply_rate)


def validate_invoice_rate_overrides(doc, method=None):
	if doc.doctype != "Sales Invoice" or can_manage_prices():
		return
	for row in doc.items:
		if (
			frappe.get_cached_value("Item", row.item_code, "item_group") == SPARE_PARTS_ITEM_GROUP
			and not row.get("pricing_rule")
			and abs(flt(row.rate) - flt(row.price_list_rate)) > 0.000001
		):
			frappe.throw(_("You are not permitted to override spare-parts invoice rates."), frappe.PermissionError)
