"""Access control and token selection for the whitelisted VFD token endpoint."""

import frappe
from frappe.tests import IntegrationTestCase

from vfd_tz.tests.utils import TEST_COMPANY, clear_vfd_records, make_registration, make_token
from vfd_tz.vfd_tz.doctype.vfd_token.vfd_token import get_token

UNPRIVILEGED_USER = "vfd-no-roles@example.com"


class TestWhitelistedEndpointPermissions(IntegrationTestCase):
	def setUp(self):
		clear_vfd_records()
		if not frappe.db.exists("User", UNPRIVILEGED_USER):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": UNPRIVILEGED_USER,
					"first_name": "No Roles",
					"send_welcome_email": 0,
				}
			)
			user.insert(ignore_permissions=True)
		registration = make_registration()
		make_token(registration, access_token="tra-secret-token")

	def tearDown(self):
		frappe.set_user("Administrator")
		clear_vfd_records()
		frappe.db.rollback()

	def test_get_token_is_denied_to_a_user_without_vfd_access(self):
		frappe.set_user(UNPRIVILEGED_USER)

		self.assertFalse(frappe.has_permission("VFD Registration"))
		with self.assertRaises(frappe.PermissionError):
			get_token(TEST_COMPANY)

	def test_get_token_still_works_for_a_system_manager(self):
		frappe.set_user("Administrator")

		token_data = get_token(TEST_COMPANY)

		self.assertEqual(token_data["token"], "bearer tra-secret-token")


class TestTokenSelection(IntegrationTestCase):
	"""v16 changed the implicit order of get_all from `modified` to `creation`."""

	def setUp(self):
		clear_vfd_records()

	def tearDown(self):
		clear_vfd_records()
		frappe.db.rollback()

	def test_token_lookup_prefers_the_latest_valid_token(self):
		registration = make_registration()
		make_token(registration, access_token="stale-token", hours=1)
		make_token(registration, access_token="fresh-token", hours=9)

		token_data = get_token(TEST_COMPANY)

		self.assertEqual(token_data["token"], "bearer fresh-token")
