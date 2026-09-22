# Copyright (c) 2020, Aakvatech and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from vfd_tz.tests.utils import TEST_COMPANY, clear_vfd_records, make_registration, make_token
from vfd_tz.vfd_tz.doctype.vfd_token.vfd_token import get_token


class TestVFDToken(IntegrationTestCase):
	def setUp(self):
		clear_vfd_records()

	def tearDown(self):
		clear_vfd_records()
		frappe.db.rollback()

	def test_no_registration_returns_nothing(self):
		self.assertIsNone(get_token(TEST_COMPANY))

	def test_a_valid_token_is_reused_without_calling_tra(self):
		registration = make_registration()
		make_token(registration, access_token="cached-token")

		token_data = get_token(TEST_COMPANY)

		self.assertEqual(token_data["token"], "bearer cached-token")
		self.assertEqual(token_data["doc"].name, registration.name)

	def test_an_expired_token_is_not_reused(self):
		registration = make_registration()
		token = make_token(registration, access_token="expired-token")
		frappe.db.set_value("VFD Token", token.name, "expires_date", add_to_date(now_datetime(), hours=-1))

		valid = frappe.get_all(
			"VFD Token",
			filters={
				"docstatus": 1,
				"company": TEST_COMPANY,
				"expires_date": [">", now_datetime()],
			},
		)

		self.assertEqual(valid, [])
