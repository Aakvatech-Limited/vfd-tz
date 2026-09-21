# Copyright (c) 2022, Aakvatech and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from vfd_tz.vfd_tz.api.sales_invoice import get_payments


class TestVFDTaxInvoice(UnitTestCase):
	"""Payment mapping shared by Sales Invoice and VFD Tax Invoice postings."""

	def _payment(self, mode, amount):
		return frappe._dict(mode_of_payment=mode, base_amount=amount)

	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.get_value")
	def test_payments_are_mapped_to_their_vfd_type(self, mock_get_value):
		mock_get_value.return_value = "CASH"

		payments = get_payments([self._payment("Cash", 1180)], 1180)

		self.assertEqual(payments, [{"PMTTYPE": "CASH"}, {"PMTAMOUNT": 1180.0}])

	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.get_value")
	def test_an_unmapped_mode_of_payment_is_rejected(self, mock_get_value):
		mock_get_value.return_value = None

		with self.assertRaises(frappe.ValidationError):
			get_payments([self._payment("Cheque", 100)], 100)

	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.get_value")
	def test_the_unpaid_balance_is_reported_as_an_invoice_payment(self, mock_get_value):
		mock_get_value.return_value = "CASH"

		payments = get_payments([self._payment("Cash", 500)], 1180)

		self.assertEqual(payments[-2:], [{"PMTTYPE": "INVOICE"}, {"PMTAMOUNT": 680.0}])

	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.get_value")
	def test_a_fully_paid_invoice_adds_no_balance_row(self, mock_get_value):
		mock_get_value.return_value = "CASH"

		payments = get_payments([self._payment("Cash", 1180)], 1180)

		self.assertNotIn({"PMTTYPE": "INVOICE"}, payments)
