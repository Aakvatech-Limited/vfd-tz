import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from vfd_tz.vfd_tz.api.sales_invoice import (
	_recover_successful_vfd_posting,
	get_itemised_tax_breakup_data,
	get_itemised_tax_from_details,
	posting_vfd_invoice,
)


class TestSalesInvoiceTaxBreakup(FrappeTestCase):
	def _make_tax_doc(self, rate=18, amount=180):
		return frappe._dict(
			items=[
				frappe._dict(
					name="ITEM-ROW-1",
					item_code="TEST-ITEM-1",
				)
			],
			taxes=[
				frappe._dict(
					name="TAX-ROW-1",
					description="VAT 18%",
					account_head="VAT - TEST",
					category="Total",
				)
			],
			item_wise_tax_details=[
				frappe._dict(
					item_row="ITEM-ROW-1",
					tax_row="TAX-ROW-1",
					rate=rate,
					amount=amount,
				)
			],
		)

	def test_item_wise_tax_details_are_mapped_to_item_code(self):
		doc = self._make_tax_doc()

		tax_data = get_itemised_tax_breakup_data(doc)

		self.assertIn("TEST-ITEM-1", tax_data)
		self.assertEqual(tax_data["TEST-ITEM-1"]["VAT 18%"].tax_rate, 18)
		self.assertEqual(tax_data["TEST-ITEM-1"]["VAT 18%"].tax_amount, 180)

	def test_tax_account_can_be_included(self):
		doc = self._make_tax_doc()

		tax_data = get_itemised_tax_from_details(doc, with_tax_account=True)

		self.assertEqual(
			tax_data["TEST-ITEM-1"]["VAT 18%"].tax_account,
			"VAT - TEST",
		)

	def test_legacy_json_item_wise_tax_detail_fallback_is_preserved(self):
		doc = frappe._dict(
			items=[],
			item_wise_tax_details=[],
			taxes=[
				frappe._dict(
					name="TAX-ROW-1",
					description="VAT 18%",
					account_head="VAT - TEST",
					category="Total",
					item_wise_tax_detail=json.dumps({"TEST-ITEM-1": [18, 180]}),
				)
			],
		)

		tax_data = get_itemised_tax_breakup_data(doc)

		self.assertEqual(tax_data["TEST-ITEM-1"]["VAT 18%"].tax_rate, 18)
		self.assertEqual(tax_data["TEST-ITEM-1"]["VAT 18%"].tax_amount, 180)


class TestSalesInvoiceVFDPosting(FrappeTestCase):
	def _make_invoice_doc(self):
		doc = MagicMock()
		doc.name = "ACC-SINV-TEST-0001"
		doc.docstatus = 1
		doc.vfd_posting_info = ""
		doc.vfd_status = "Pending"
		doc.flags = frappe._dict()
		return doc

	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.db.commit")
	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.get_all")
	def test_recover_successful_vfd_posting_links_existing_ack(self, mock_get_all, mock_commit):
		doc = self._make_invoice_doc()
		mock_get_all.return_value = [frappe._dict(name="VFDP-26-000438", rctnum=727)]

		result = _recover_successful_vfd_posting(doc)

		self.assertTrue(result)
		self.assertEqual(doc.vfd_posting_info, "VFDP-26-000438")
		self.assertEqual(doc.vfd_status, "Success")
		self.assertTrue(doc.flags.ignore_links)
		doc.save.assert_called_once_with(ignore_permissions=True)
		mock_commit.assert_called_once()

	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.get_all")
	def test_recover_successful_vfd_posting_returns_false_when_none_exist(self, mock_get_all):
		doc = self._make_invoice_doc()
		mock_get_all.return_value = []

		result = _recover_successful_vfd_posting(doc)

		self.assertFalse(result)
		doc.save.assert_not_called()

	@patch("vfd_tz.vfd_tz.api.sales_invoice.requests.request")
	@patch("vfd_tz.vfd_tz.api.sales_invoice.get_token")
	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.get_all")
	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.get_doc")
	def test_existing_successful_ack_prevents_reposting_to_tra(
		self, mock_get_doc, mock_get_all, mock_get_token, mock_request
	):
		doc = self._make_invoice_doc()
		mock_get_doc.return_value = doc
		mock_get_all.return_value = [frappe._dict(name="VFDP-26-000438", rctnum=727)]

		result = posting_vfd_invoice(doc.name)

		self.assertEqual(result, "Success")
		self.assertEqual(doc.vfd_posting_info, "VFDP-26-000438")
		self.assertEqual(doc.vfd_status, "Success")
		mock_get_token.assert_not_called()
		mock_request.assert_not_called()

	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.db.commit")
	@patch("vfd_tz.vfd_tz.api.sales_invoice.frappe.get_all")
	def test_recovery_save_failure_does_not_commit(self, mock_get_all, mock_commit):
		doc = self._make_invoice_doc()
		mock_get_all.return_value = [frappe._dict(name="VFDP-26-000438", rctnum=727)]
		doc.save.side_effect = frappe.ValidationError("save failed")

		with self.assertRaises(frappe.ValidationError):
			_recover_successful_vfd_posting(doc)

		mock_commit.assert_not_called()
