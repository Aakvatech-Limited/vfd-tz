# Copyright (c) 2020, Aakvatech and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from vfd_tz.tests.utils import TEST_COMPANY, clear_vfd_records, make_registration
from vfd_tz.vfd_tz.doctype.vfd_uin.vfd_uin import get_counters


class TestVFDUIN(IntegrationTestCase):
	def setUp(self):
		clear_vfd_records()
		make_registration()

	def tearDown(self):
		clear_vfd_records()
		frappe.db.rollback()

	def test_first_call_seeds_counters_from_the_registration(self):
		counters = get_counters(TEST_COMPANY)

		self.assertEqual(counters.name, TEST_COMPANY)
		self.assertEqual(counters.gc, 100)
		self.assertEqual(counters.dc, 1)

	def test_counters_increment_on_every_call(self):
		first = get_counters(TEST_COMPANY)
		gc, dc = first.gc, first.dc

		second = get_counters(TEST_COMPANY)

		self.assertEqual(second.gc, gc + 1)
		self.assertEqual(second.dc, dc + 1)

	def test_daily_counter_resets_on_a_new_day(self):
		counters = get_counters(TEST_COMPANY)
		frappe.db.set_value("VFD UIN", counters.name, "dc_date", add_days(nowdate(), -1))
		frappe.db.set_value("VFD UIN", counters.name, "dc", 42)

		refreshed = get_counters(TEST_COMPANY)

		self.assertEqual(refreshed.dc, 1)
		self.assertEqual(getdate(refreshed.dc_date), getdate(nowdate()))

	def test_global_counter_does_not_reset_on_a_new_day(self):
		counters = get_counters(TEST_COMPANY)
		gc = counters.gc
		frappe.db.set_value("VFD UIN", counters.name, "dc_date", add_days(nowdate(), -1))

		refreshed = get_counters(TEST_COMPANY)

		self.assertEqual(refreshed.gc, gc + 1)

	def test_uin_cannot_be_deleted(self):
		get_counters(TEST_COMPANY)

		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("VFD UIN", TEST_COMPANY)
