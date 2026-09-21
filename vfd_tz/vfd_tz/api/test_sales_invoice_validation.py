from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from vfd_tz.vfd_tz.api.sales_invoice_validation import (
	_get_calculated_item_wise_tax_details,
	vfd_validation,
)


class DummyDoc:
	def __init__(self, **values):
		self.values = values

	def get(self, key, default=None):
		return self.values.get(key, default)

	def set(self, key, value):
		self.values[key] = value


class TestSalesInvoiceBeforeSubmitValidation(FrappeTestCase):
	def _make_calculated_row(self):
		return frappe._dict(
			{
				"item": frappe._dict(name="ITEM-ROW-1"),
				"tax": frappe._dict(name="TAX-ROW-1"),
				"rate": 18,
				"amount": 180,
				"taxable_amount": 1000,
			}
		)

	def test_calculated_rows_are_converted_to_persisted_shape(self):
		doc = DummyDoc(_item_wise_tax_details=[self._make_calculated_row()])

		details = _get_calculated_item_wise_tax_details(doc)

		self.assertEqual(len(details), 1)
		self.assertEqual(details[0].item_row, "ITEM-ROW-1")
		self.assertEqual(details[0].tax_row, "TAX-ROW-1")
		self.assertEqual(details[0].rate, 18)
		self.assertEqual(details[0].amount, 180)
		self.assertEqual(details[0].taxable_amount, 1000)

	@patch("vfd_tz.vfd_tz.api.sales_invoice_validation._vfd_validation")
	def test_before_submit_uses_calculated_rows_and_restores_child_table(self, mock_validation):
		original_details = [frappe._dict(item_row="OLD-ITEM", tax_row="OLD-TAX")]
		doc = DummyDoc(
			_item_wise_tax_details=[self._make_calculated_row()],
			item_wise_tax_details=original_details,
		)

		def assert_temporary_details(validation_doc, method):
			details = validation_doc.get("item_wise_tax_details")
			self.assertEqual(details[0].item_row, "ITEM-ROW-1")
			self.assertEqual(details[0].tax_row, "TAX-ROW-1")

		mock_validation.side_effect = assert_temporary_details

		vfd_validation(doc, "before_submit")

		self.assertIs(doc.get("item_wise_tax_details"), original_details)

	@patch("vfd_tz.vfd_tz.api.sales_invoice_validation._vfd_validation")
	def test_falls_back_when_no_calculated_rows_exist(self, mock_validation):
		persisted = [frappe._dict(item_row="ITEM-ROW-1", tax_row="TAX-ROW-1")]
		doc = DummyDoc(_item_wise_tax_details=[], item_wise_tax_details=persisted)

		vfd_validation(doc, "before_submit")

		mock_validation.assert_called_once_with(doc, "before_submit")
		self.assertIs(doc.get("item_wise_tax_details"), persisted)
