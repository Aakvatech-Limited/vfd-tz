# Copyright (c) 2020, Aakvatech and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from vfd_tz.api.utils import get_latest_registration_doc
from vfd_tz.tests.utils import TEST_COMPANY, clear_vfd_records, make_registration


class TestVFDRegistration(IntegrationTestCase):
	def setUp(self):
		clear_vfd_records()

	def tearDown(self):
		clear_vfd_records()
		frappe.db.rollback()

	def test_cancelling_marks_the_registration_inactive(self):
		registration = make_registration()

		registration.cancel()

		self.assertEqual(frappe.db.get_value("VFD Registration", registration.name, "r_status"), "Inactive")

	def test_no_active_registration_throws_by_default(self):
		with self.assertRaises(frappe.ValidationError):
			get_latest_registration_doc(TEST_COMPANY)

	def test_no_active_registration_returns_none_when_not_throwing(self):
		self.assertIsNone(get_latest_registration_doc(TEST_COMPANY, throw=False))

	def test_inactive_registration_is_not_returned(self):
		make_registration(r_status="Inactive")

		self.assertIsNone(get_latest_registration_doc(TEST_COMPANY, throw=False))

	def test_blocked_registration_throws(self):
		make_registration(is_blocked=1, tra_message="Blocked by TRA")

		with self.assertRaises(frappe.ValidationError):
			get_latest_registration_doc(TEST_COMPANY)
