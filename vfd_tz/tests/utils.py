"""Shared fixtures for the vfd_tz test suite."""

import frappe
from frappe.utils import add_to_date, now_datetime
from frappe.utils.password import set_encrypted_password

TEST_COMPANY = "_Test Company"
TEST_CERT_SERIAL = "aa bb cc dd"


def make_registration(company=TEST_COMPANY, submit=True, **overrides):
	"""Create a VFD Registration without touching the certificate on disk."""
	values = {
		"doctype": "VFD Registration",
		"company": company,
		"url": "https://vfd.example.invalid",
		"tin": "123456789",
		"certkey": "test-certkey",
		"certificate_password": "test-certpass",
		"verification_url": "https://verify.example.invalid/",
		"vfd_start_date": add_to_date(now_datetime(), years=-1),
		"r_status": "Active",
		"gc": "100",
		"receiptcode": "RC",
		"serial": "10TZ000000",
		"vrn": "40-123456-X",
		"cert_serial": TEST_CERT_SERIAL,
	}
	values.update(overrides)

	doc = frappe.get_doc(values)
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	# cert_serial is a Password field, so it is stored outside the row.
	set_encrypted_password("VFD Registration", doc.name, TEST_CERT_SERIAL, "cert_serial")
	if submit:
		frappe.db.set_value("VFD Registration", doc.name, "docstatus", 1)
		doc.reload()
	return doc


def make_token(registration, company=TEST_COMPANY, access_token="test-token", hours=5):
	doc = frappe.get_doc(
		{
			"doctype": "VFD Token",
			"company": company,
			"vfd_registration": registration.name,
			"posting_date": now_datetime(),
			"expires_in": hours * 3600,
			"expires_date": add_to_date(now_datetime(), hours=hours),
			"access_token": access_token,
		}
	)
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	frappe.db.set_value("VFD Token", doc.name, "docstatus", 1)
	doc.reload()
	return doc


def clear_vfd_records(company=TEST_COMPANY):
	frappe.db.delete("VFD Token", {"company": company})
	frappe.db.delete("VFD Registration", {"company": company})
	frappe.db.delete("VFD UIN", {"company": company})
