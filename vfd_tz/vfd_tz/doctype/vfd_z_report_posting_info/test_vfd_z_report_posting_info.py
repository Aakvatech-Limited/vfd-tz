# Copyright (c) 2020, Aakvatech and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


class TestVFDZReportPostingInfo(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_posting_info_records_the_tra_acknowledgement(self):
		doc = frappe.get_doc(
			{
				"doctype": "VFD Z Report Posting Info",
				"vfd_z_report": "VFDZR-26-01-001",
				"ackcode": 0,
				"ackmsg": "Received",
				"znumber": 7,
			}
		)
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)

		self.assertTrue(doc.name.startswith("VFDZRP-"))
		self.assertEqual(doc.ackcode, 0)
		self.assertEqual(doc.znumber, 7)
