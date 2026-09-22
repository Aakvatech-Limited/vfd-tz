"""Regressions for the Frappe version-16 behaviour changes that affect vfd_tz."""

import warnings

import frappe
from frappe.tests import IntegrationTestCase

from vfd_tz.api.utils import get_latest_registration_doc
from vfd_tz.tests.utils import TEST_COMPANY, clear_vfd_records, make_registration


class TestDefaultOrderingChange(IntegrationTestCase):
	"""v16 changed the implicit order of get_all from `modified` to `creation`."""

	def setUp(self):
		clear_vfd_records()

	def tearDown(self):
		clear_vfd_records()
		frappe.db.rollback()

	def test_latest_registration_follows_an_explicit_order(self):
		older = make_registration(serial="10TZ000001")
		newer = make_registration(serial="10TZ000002")

		# Touch the older row so `modified desc` and `creation desc` disagree.
		frappe.db.set_value("VFD Registration", older.name, "vrn", "40-999999-Z")

		selected = get_latest_registration_doc(TEST_COMPANY, throw=False)

		self.assertEqual(
			selected.name,
			newer.name,
			"get_latest_registration_doc must pick the newest registration regardless of "
			"which row was modified last",
		)


class TestTransactionControlInDocumentHooks(IntegrationTestCase):
	"""v16 disables commit/rollback while document hooks run."""

	def test_commit_is_ignored_inside_a_document_hook(self):
		frappe.db._disable_transaction_control += 1
		try:
			with warnings.catch_warnings(record=True) as raised:
				warnings.simplefilter("always")
				frappe.db.commit()
		finally:
			frappe.db._disable_transaction_control -= 1

		self.assertTrue(
			any("disabled during certain events" in str(w.message) for w in raised),
			"frappe.db.commit() is silently ignored inside doc_events on v16; VFD code must "
			"not rely on it to make counters visible to a background worker",
		)

	def test_vfd_posting_is_enqueued_only_after_the_transaction_commits(self):
		from vfd_tz.vfd_tz.api import sales_invoice

		source = frappe.read_file(sales_invoice.__file__)

		self.assertIn(
			"enqueue_after_commit=True",
			source,
			"the VFD posting job must be queued after commit, otherwise the worker can read "
			"the invoice before its VFD counters are visible",
		)
