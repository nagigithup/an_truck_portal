from uuid import uuid4

import frappe
from frappe.tests import IntegrationTestCase

from an_truck_portal.api import spare_parts as api


class TestItemCatalog(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.user = frappe.session.user
		frappe.set_user("Administrator")
		frappe.db.savepoint("portal_item_catalog")

	def tearDown(self):
		frappe.db.rollback(save_point="portal_item_catalog")
		frappe.set_user(self.user)
		super().tearDown()

	def data(self):
		return {
			"item_code": "00-PART." + uuid4().hex[:10], "item_name": "Portal item test",
			"item_group": api.SPARE_PARTS_ITEM_GROUP,
			"stock_uom": frappe.db.get_value("UOM", {"enabled": 1}, "name"),
		}

	def test_new_item_stock_default_and_explicit_choice(self):
		for choice in (None, 0, 1):
			with self.subTest(choice=choice):
				data = self.data()
				if choice is not None:
					data["is_stock_item"] = choice
				result = api.save_item(data)
				item = frappe.get_doc("Item", result["name"])
				self.assertEqual(item.item_code, data["item_code"])
				self.assertEqual(item.is_stock_item, 1 if choice is None else choice)

	def test_stock_choice_and_disabled_value_reload(self):
		data = self.data()
		data.update({"is_stock_item": 0, "disabled": 1})
		created = api.save_item(data)
		form = api.get_item_form(created["name"])
		self.assertEqual(form["record"]["is_stock_item"], 0)
		self.assertEqual(form["record"]["disabled"], 1)
		api.save_item({"is_stock_item": 1, "disabled": 0}, name=created["name"], modified=form["modified"])
		updated = api.get_item_form(created["name"])
		self.assertEqual(updated["record"]["is_stock_item"], 1)
		self.assertEqual(updated["record"]["disabled"], 0)

	def test_truck_catalog_uses_existing_group_and_vin_serial_tracking(self):
		from an_truck.services import is_vehicle_item
		form = api.get_item_form(catalog="trucks")
		data = self.data()
		data["item_group"] = form["record"]["item_group"]
		result = api.save_item(data, catalog="trucks")
		item = frappe.get_doc("Item", result["name"])
		self.assertEqual(item.is_stock_item, 1)
		self.assertEqual(item.has_serial_no, 1)
		self.assertTrue(is_vehicle_item(item.name))
		self.assertIn(item.name, [row.name for row in api.list_items(catalog="trucks", search=item.item_code)["rows"]])
		self.assertNotIn(item.name, [row.name for row in api.list_items(search=item.item_code)["rows"]])
		with self.assertRaises(frappe.PermissionError):
			api.get_item_form(item.name)

	def test_catalog_boundaries_and_non_stock_truck_are_rejected(self):
		truck_group = api.get_item_form(catalog="trucks")["record"]["item_group"]
		data = self.data()
		data["item_group"] = truck_group
		with self.assertRaises(frappe.ValidationError):
			api.save_item(data)
		data["is_stock_item"] = 0
		with self.assertRaises(frappe.ValidationError):
			api.save_item(data, catalog="trucks")
		self.assertFalse(frappe.db.exists("Item", data["item_code"]))
		with self.assertRaises(frappe.ValidationError):
			api.list_items(catalog="other")
