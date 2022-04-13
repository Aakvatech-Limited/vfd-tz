# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, add_to_date, now_datetime
from api.utlis import to_base64, get_latest_registration_doc
from vfd_tz.vfd_tz.doctype.vfd_registration.vfd_registration import auto_reregistration
import requests
import json


class VFDToken(Document):
    pass


@frappe.whitelist()
def get_token(company):
    token_data = {}
    doc = get_latest_registration_doc(company, throw=False)
    if not doc:
        return
    token_data["cert_serial"] = to_base64(doc.get_password("cert_serial"))
    token_data["doc"] = doc

    token_list = frappe.get_all(
        "VFD Token",
        filters={
            "docstatus": 1,
            "company": company,
            "vfd_registration": doc.name,
            "expires_date": [">", now_datetime()],
        },
        fields=["name", "access_token"],
    )

    if len(token_list):
        token_data["token"] = "bearer " + token_list[0]["access_token"]

    else:
        url = doc.url + "/vfdtoken"
        data = {
            "Username": doc.get_password("username"),
            "Password": doc.get_password("password"),
            "grant_type": "password",
        }
        response = requests.request("POST", url, data=data, timeout=5)
        token_header = frappe._dict(response.headers)
        token_data = json.loads(response.text)
        token_doc = frappe.get_doc(
            {
                "doctype": "VFD Token",
                "company": doc.company,
                "vfd_registration": doc.name,
                "posting_date": now_datetime(),
                "expires_in": int(token_data.get("expires_in") or 0),
                "expires_date": add_to_date(
                    now(), seconds=(int(token_data.get("expires_in") or 0) - 1000)
                ),
                "access_token": token_data.get("access_token"),
                "ackcode": token_header.get("ACKCODE"),
                "ackmsg": token_header.get("ACKMSG"),
            }
        )

        token_doc.flags.ignore_permissions = True
        token_doc.insert(ignore_permissions=True)
        token_doc.submit()
        if token_doc.ackcode == "8":
            frappe.log_error(
                "ACKCODE: {} - ACKMSG: {}".format(token_doc.ackcode, token_doc.ackmsg),
                "BLOCK ACKCODE found",
            )
            doc.do_not_send_vfd = 1
            doc.send_vfd_z_report = 0
            doc.is_blocked = 1
        elif token_doc.ackcode == "7":
            doc.do_not_send_vfd = 0
            doc.send_vfd_z_report = 1
            doc.is_blocked = 0
        elif token_doc.ackcode == "18":
            doc.do_not_send_vfd = 1
            doc.send_vfd_z_report = 0
            doc.is_blocked = 1
            doc.r_status = "Inactive"
            # Auto re-registration
            auto_reregistration(doc)
        else:
            frappe.log_error(
                "{} - {}".format(token_doc.ackcode, token_doc.ackmsg), "ackcode normal"
            )
        doc.tra_message = token_doc.ackmsg
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        if token_doc.ackcode in ["8", "18"]:
            frappe.log_error(
                _(
                    "TRA has rejected the token request with code {0} and message {1}"
                ).format(token_doc.ackcode, token_doc.ackmsg),
                "VFD Command Found",
            )
        token_data["token"] = "bearer " + (token_data.get("access_token") or "")

    return token_data


def check_vfd_status():
    doc_list = frappe.get_all(
        "VFD Registration",
        filters={"docstatus": 1, "r_status": "Active"},
        pluck="company",
    )
    for company in doc_list:
        try:
            get_token(company)
        except Exception as e:
            frappe.log_error(
                _("VFD Token not received {0}").format(company),
                "VFD Token Not Found",
            )
