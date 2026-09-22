"""Custom fields must survive a fresh install, not only a migrate."""

import frappe
from frappe.tests import IntegrationTestCase


class TestSalesInvoiceCustomFields(IntegrationTestCase):
	def test_send_serial_no_to_tra_field_exists(self):
		self.assertTrue(
			frappe.db.exists("Custom Field", {"dt": "Sales Invoice", "fieldname": "send_serial_no_to_tra"}),
			"Sales Invoice.send_serial_no_to_tra is missing; install_app marks patches as "
			"completed without running them, so the field must ship as a fixture",
		)
