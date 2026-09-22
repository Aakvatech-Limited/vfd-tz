# Copyright (c) 2021, Aakvatech and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from vfd_tz.vfd_tz.doctype.vfd_z_report.vfd_z_report import get_vattotals


class TestVFDZReportVatTotals(UnitTestCase):
	"""Z Report VAT totals always report all five tax codes, in TRA order."""

	def _sales_invoice_item(self, net_amount):
		return frappe._dict(
			parenttype="Sales Invoice",
			parent="ACC-SINV-TEST-0001",
			item_tax_template="TT",
			item_code="ITEM",
			base_net_amount=net_amount,
		)

	def _tax_invoice_item(self, taxcode, unit_price, unit_tax):
		return frappe._dict(
			parenttype="VFD Tax Invoice",
			item_taxcode=taxcode,
			unit_price=unit_price,
			unit_tax=unit_tax,
		)

	@patch("vfd_tz.vfd_tz.doctype.vfd_z_report.vfd_z_report.get_item_taxcode")
	def test_standard_rate_items_are_taxed_at_18_percent(self, mock_taxcode):
		mock_taxcode.return_value = 1

		totals = get_vattotals([self._sales_invoice_item(1000)], "40-123456-X")

		self.assertEqual(totals[0], {"vatrate": "A-18.00", "nettamount": 1000.0, "taxamount": 180.0})

	@patch("vfd_tz.vfd_tz.doctype.vfd_z_report.vfd_z_report.get_item_taxcode")
	def test_all_five_tax_codes_are_always_reported(self, mock_taxcode):
		mock_taxcode.return_value = 1

		totals = get_vattotals([self._sales_invoice_item(1000)], "40-123456-X")

		self.assertEqual(
			[row["vatrate"] for row in totals],
			["A-18.00", "B-0.00", "C-0.00", "D-0.00", "E-0.00"],
		)

	@patch("vfd_tz.vfd_tz.doctype.vfd_z_report.vfd_z_report.get_item_taxcode")
	def test_non_standard_rate_items_carry_no_tax(self, mock_taxcode):
		mock_taxcode.return_value = 2

		totals = get_vattotals([self._sales_invoice_item(500)], "40-123456-X")

		self.assertEqual(totals[1], {"vatrate": "B-0.00", "nettamount": 500.0, "taxamount": 0.0})

	@patch("vfd_tz.vfd_tz.doctype.vfd_z_report.vfd_z_report.get_item_taxcode")
	def test_an_unregistered_vrn_reports_zero_tax(self, mock_taxcode):
		mock_taxcode.return_value = 1

		totals = get_vattotals([self._sales_invoice_item(1000)], "NOT REGISTERED")

		self.assertEqual(totals[0], {"vatrate": "A-18.00", "nettamount": 1000.0, "taxamount": 0.0})

	@patch("vfd_tz.vfd_tz.doctype.vfd_z_report.vfd_z_report.get_item_taxcode")
	def test_amounts_are_accumulated_per_tax_code(self, mock_taxcode):
		mock_taxcode.side_effect = [1, 1, 2]

		totals = get_vattotals(
			[self._sales_invoice_item(1000), self._sales_invoice_item(500), self._sales_invoice_item(250)],
			"40-123456-X",
		)

		self.assertEqual(totals[0], {"vatrate": "A-18.00", "nettamount": 1500.0, "taxamount": 270.0})
		self.assertEqual(totals[1], {"vatrate": "B-0.00", "nettamount": 250.0, "taxamount": 0.0})

	def test_tax_invoice_items_use_their_own_unit_amounts(self):
		totals = get_vattotals(
			[self._tax_invoice_item("1", 1000, 180), self._tax_invoice_item("2", 500, 0)],
			"40-123456-X",
		)

		self.assertEqual(totals[0], {"vatrate": "A", "nettamount": 1000.0, "taxamount": 180.0})
		self.assertEqual(totals[1], {"vatrate": "B", "nettamount": 500.0, "taxamount": 0.0})
