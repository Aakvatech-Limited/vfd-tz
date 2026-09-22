# Copyright (c) 2020, Aakvatech and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import UnitTestCase

from vfd_tz.vfd_tz.api.sales_invoice import _recover_successful_vfd_posting


class TestVFDInvoicePostingInfo(UnitTestCase):
	"""Recovery of an acknowledged posting must never re-send the receipt to TRA."""

	def _make_invoice(self):
		doc = MagicMock()
		doc.name = "ACC-SINV-TEST-0001"
		doc.docstatus = 1
		doc.vfd_posting_info = ""
		doc.vfd_status = "Pending"
		doc.flags = frappe._dict()
		return doc

	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.db.commit")
	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.get_all")
	def test_only_acknowledged_postings_are_recovered(self, mock_get_all, mock_commit):
		_recover_successful_vfd_posting(self._make_invoice())

		filters = mock_get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["ackcode"], 0)

	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.db.commit")
	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.get_all")
	def test_recovery_picks_the_newest_posting_explicitly(self, mock_get_all, mock_commit):
		_recover_successful_vfd_posting(self._make_invoice())

		self.assertEqual(mock_get_all.call_args.kwargs["order_by"], "creation desc")
		self.assertEqual(mock_get_all.call_args.kwargs["page_length"], 1)
