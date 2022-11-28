# Copyright (c) 2022, Aakvatech and contributors
# For license information, please see license.txt

from frappe.model.document import Document
import frappe
from frappe import _
from vfd_tz.vfd_tz.doctype.vfd_token.vfd_token import get_token
from vfd_tz.api.xml import xml_to_dic, dict_to_xml
from vfd_tz.api.utils import (
    get_signature,
    remove_special_characters,
    get_latest_registration_doc,
    remove_all_except_numbers,
)
import requests
from frappe.utils import flt, nowdate, nowtime, format_datetime
from vfd_tz.vfd_tz.doctype.vfd_uin.vfd_uin import get_counters
from frappe.utils.background_jobs import enqueue
# import json
# import time


class VFDTaxInvoice(Document):
    def before_submit(self):
        if self.is_return or self.is_not_vfd_invoice:
            return
        # if doc.base_net_total == 0:
        # 	frappe.throw(_("Base net amount is zero. Correct the invoice and retry."))

        registration_doc = get_latest_registration_doc(self.company, throw=False)
        if not registration_doc:
            return

        # tax_data = get_itemised_tax_breakup_html(doc)
        # if not tax_data:
        # 	frappe.throw(_("Taxes not set correctly"))

        # tax_rate_map = {"1": 18, "2": 0, "3": 0, "4": 0, "5": 0}
        for item in self.items:
            if not item.item_name:
                frappe.throw(_("Item Name not set for item {0}".format(item.item_name)))
            item_taxcode = item.item_taxcode

            if item_taxcode == 1 and registration_doc.vrn == "NOT REGISTERED":
                frappe.throw(
                    _(
                        "Taxes SHOULD not set to 18pct for Standard Rate item {0} for NON VAT company".format(
                            item.item_name
                        )
                    )
                )


    def after_insert(self):
        if self.docstatus == 1 and self.is_auto_generate_vfd == True:
            enqueue_posting_vfd_invoice(self.name)
            self.reload()

    def on_submit(self):
        if self.is_auto_generate_vfd == True:
            enqueue_posting_vfd_invoice(self.name)
            frappe.msgprint(
                _("Auto generated VFD for invoice {0}".format(self.name)), alert=True
            )


    def on_cancel(self):
        if self.vfd_rctnum:
            frappe.throw(_("This invoice cannot be canceled"))


@frappe.whitelist()
def enqueue_posting_vfd_invoice(invoice_name):
    doc = frappe.get_doc("VFD Tax Invoice", invoice_name)
    if doc.is_return or doc.is_not_vfd_invoice:
        return
    registration_doc = get_latest_registration_doc(doc.company)
    if doc.creation < registration_doc.vfd_start_date:
        frappe.throw(
            _(
                "VFD Tax Invoice creation older than VFD Registration date! Cannot submit VFD to TRA."
            )
        )
    if doc.posting_date < registration_doc.vfd_start_date.date():
        frappe.throw(
            _(
                "VFD Tax Invoice posting date older than VFD Registration date! Cannot submit VFD to TRA."
            )
        )
    if not doc.vfd_rctnum:
        counters = get_counters(doc.company)
        doc.vfd_gc = counters.gc
        doc.vfd_rctnum = counters.gc
        doc.vfd_dc = counters.dc
        doc.vfd_date = nowdate()
        doc.vfd_time = nowtime()
        doc.vfd_serial = registration_doc.serial
        doc.vfd_rctvnum = str(registration_doc.receiptcode) + str(doc.vfd_gc)
        doc.vfd_verification_url = (
            registration_doc.verification_url
            + doc.vfd_rctvnum
            + "_"
            + format_datetime(str(doc.vfd_time), "HHmmss")
        )
        if doc.vfd_status == "Not Sent":
            doc.vfd_status = "Pending"
        doc.db_update()
        frappe.db.commit()
        frappe.msgprint(_("Registered Invoice to be sent to TRA VFD System"))
    if not frappe.local.flags.vfd_posting:
        enqueue(
            method=posting_all_vfd_invoices, queue="short", timeout=10000, is_async=True
        )
    else:
        frappe.log_error(_("VFD Invoice posting already in progress"))
    return True


def posting_all_vfd_invoices_off_peak():
    posting_all_vfd_invoices()


def posting_all_vfd_invoices():
    if frappe.local.flags.vfd_posting:
        frappe.log_error(_("VFD Posting Flag found", "VFD Posting Flag found"))
        return
    frappe.local.flags.vfd_posting = True
    company_list = frappe.get_all("Company")
    for company in company_list:
        registration_doc = get_latest_registration_doc(company["name"], throw=False)
        if not registration_doc:
            continue
        if registration_doc.do_not_send_vfd:
            continue
        invoices_list = frappe.get_all(
            "VFD Tax Invoice",
            filters={
                "docstatus": 1,
                "is_return": 0,
                "company": company.name,
                "vfd_posting_info": "",
                "vfd_status": ["in", ["Failed", "Pending"]],
            },
            fields={"name", "vfd_rctnum", "vfd_gc"},
            order_by="vfd_gc ASC",
        )
        # Find out last invoice to ensure next GC is correctly sent
        last_invoices_list = frappe.get_all(
            "VFD Tax Invoice",
            filters={
                "docstatus": 1,
                "is_return": 0,
                "company": company.name,
                "vfd_posting_info": ["!=", ""],
                "vfd_status": "Success",
            },
            fields={"name", "vfd_rctnum", "vfd_gc"},
            page_length=10,
            order_by="vfd_gc DESC",
        )

        first_to_send_gc = 0
        last_sent_success_gc = 0

        if len(invoices_list) > 0:
            first_to_send_gc = invoices_list[0].get("vfd_gc")
        else:
            continue
        if len(last_invoices_list) > 0:
            last_sent_success_gc = last_invoices_list[0].get("vfd_gc")
        else:
            last_sent_success_gc = int(registration_doc.gc) - 1

        # if last_sent_success_gc + 1 != first_to_send_gc:
        #     frappe.log_error(
        #         _(
        #             "Invoice sequence out of order. Last GC Sent Successfully is {0}. First to send GC is {1}. Check failed VFD Invoice Posting Info"
        #         ).format(last_sent_success_gc, first_to_send_gc),
        #         "Invoice Sequence Error",
        #     )

        failed_receipts = 0
        for invoice in invoices_list:
            status = posting_vfd_invoice(invoice.name)
            if status != "Success":
                # As per TRA Advice on 2022-04-13 20:08 we should not stop posting if one fails
                # frappe.local.flags.vfd_posting = False
                frappe.log_error(
                    _("Error in sending VFD Invoice {0}").format(invoice.name),
                    "VFD Failed for {0}".format(company.name),
                )
                # As per TRA Advice on 2022-04-13 20:08 we should not stop posting if one fails
                # break
                failed_receipts += 1
                if failed_receipts > 3:
                    break

        frappe.local.flags.vfd_posting = False


def posting_vfd_invoice(invoice_name):
    doc = frappe.get_doc("VFD Tax Invoice", invoice_name)
    if doc.vfd_posting_info or doc.docstatus != 1:
        return
    if doc.vfd_status == "Not Sent":
        doc.vfd_status = "Pending"
        doc.db_update()
        frappe.db.commit()
        doc.reload()
    token_data = get_token(doc.company)
    registration_doc = token_data.get("doc")
    headers = {
        "Content-Type": "Application/xml",
        "Routing-Key": "vfdrct",
        "Cert-Serial": token_data["cert_serial"],
        "Authorization": token_data["token"],
    }
    # if doc.vfd_cust_id and not doc.vfd_cust_id_type:
    #     frappe.throw(
    #         _("Please make sure to set VFD Customer ID Type in Customer Master")
    #     )

    rect_data = {
        "DATE": doc.vfd_date,
        # 0:59:30.715164
        "TIME": format_datetime(str(doc.vfd_time), "HH:mm:ss"),
        "TIN": registration_doc.tin,
        "REGID": registration_doc.regid,
        "EFDSERIAL": registration_doc.serial,
        "CUSTIDTYPE": int(doc.vfd_cust_id_type[:1]),
        "CUSTID": doc.vfd_cust_id,
        "CUSTNAME": remove_special_characters(doc.client_name),
        "MOBILENUM": remove_all_except_numbers(doc.mobile_no),
        "RCTNUM": doc.vfd_gc,
        "DC": doc.vfd_dc,
        "GC": doc.vfd_gc,
        "ZNUM": format_datetime(str(doc.vfd_date), "YYYYMMdd"),
        "RCTVNUM": doc.vfd_rctvnum,
        "ITEMS": [],
        "TOTALS": {
            "TOTALTAXEXCL": flt(doc.net_total, 2),
            "TOTALTAXINCL": flt(doc.grand_total, 2),
            "DISCOUNT": flt(doc.total_discount, 2),
        },
        "PAYMENTS": get_payments(doc),
        "VATTOTALS": get_vattotals(doc.items, registration_doc.vrn),
    }
    use_item_group = registration_doc.use_item_group
    for item in doc.items:
        item_data = {
            "ID": remove_special_characters(
                item.item_group if use_item_group else item.item_name
            ),
            "DESC": remove_special_characters(
                item.item_group if use_item_group else item.item_name
            ),
            "QTY": flt(item.quantity, 2),
            "TAXCODE": item.item_taxcode,
            "AMT": flt(item.unit_subtotal, 2),
        }
        if use_item_group:
            found_item = ""
            for i in rect_data["ITEMS"]:
                if (
                    i["ITEM"]["TAXCODE"] == item_data["TAXCODE"]
                    and i["ITEM"]["ID"] == item_data["ID"]
                ):
                    found_item = i["ITEM"]
                    break
            if found_item:
                found_item["QTY"] = 1
                rounded_amount = flt(found_item["AMT"], 2)
                found_item["AMT"] = flt(rounded_amount, 2) + flt(item_data["AMT"], 2)
            else:
                item_data["QTY"] = 1
                rect_data["ITEMS"].append({"ITEM": item_data})
        else:
            rect_data["ITEMS"].append({"ITEM": item_data})

    rect_data_xml = (
        str(dict_to_xml(rect_data, "RCT")[39:])
        .replace("<None>", "")
        .replace("</None>", "")
    )

    efdms_data = {
        "RCT": rect_data,
        "EFDMSSIGNATURE": get_signature(rect_data_xml, registration_doc),
    }
    data = dict_to_xml(efdms_data).replace("<None>", "").replace("</None>", "")
    url = registration_doc.url + "/api/efdmsRctInfo"
    response = requests.request("POST", url, headers=headers, data=data, timeout=60)

    if not response.status_code == 200:
        posting_info_doc = frappe.get_doc(
            {
                "doctype": "VFD Invoice Posting Info",
                "vfd_tax_invoice": doc.name,
                "ackcode": response.status_code,
                "ackmsg": response.text,
                "date": nowdate(),
                "time": nowtime(),
                "req_headers": str(headers),
                "req_data": str(data).encode("utf8"),
            }
        )
        posting_info_doc.flags.ignore_permissions = True
        posting_info_doc.insert(ignore_permissions=True)
        doc.vfd_status = "Failed"
        doc.db_update()
        frappe.db.commit()
        return "Failed"

    xmldict = xml_to_dic(response.text)
    rctack = xmldict.get("rctack")
    posting_info_doc = frappe.get_doc(
        {
            "doctype": "VFD Invoice Posting Info",
            "vfd_tax_invoice": doc.name,
            "ackcode": rctack.get("ackcode"),
            "ackmsg": rctack.get("ackmsg"),
            "date": rctack.get("date"),
            "time": rctack.get("time"),
            "rctnum": rctack.get("rctnum"),
            "efdmssignature": xmldict.get("efdmssignature"),
            "req_headers": str(headers),
            "req_data": str(data).encode("utf8"),
        }
    )
    posting_info_doc.flags.ignore_permissions = True
    posting_info_doc.insert(ignore_permissions=True)
    frappe.db.commit()
    if int(posting_info_doc.ackcode) == 0:
        doc.vfd_posting_info = posting_info_doc.name
        doc.vfd_status = "Success"
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return "Success"
    else:
        doc.vfd_status = "Failed"
        doc.db_update()
        frappe.db.commit()
        return "Failed"


def get_payments(doc):
    payments_dict = []
    payments_dict.append({"PMTTYPE": doc.payment_type})
    payments_dict.append({"PMTAMOUNT": flt(doc.grand_total, 2)})

    return payments_dict


def get_vattotals(items, vrn):
    vattotals = {}
    tax_rate_map = {"1": 18, "2": 0, "3": 0, "4": 0, "5": 0}

    for item in items:
        item_taxcode = item.item_taxcode
        if not vattotals.get(item_taxcode):
            vattotals[item_taxcode] = {}
            vattotals[item_taxcode]["NETTAMOUNT"] = 0
            vattotals[item_taxcode]["TAXAMOUNT"] = 0
        vattotals[item_taxcode]["NETTAMOUNT"] += flt(item.unit_subtotal - item.unit_tax, 2)
        if vrn == "NOT REGISTERED":
            vattotals[item_taxcode]["TAXAMOUNT"] += 0
        else:
            vattotals[item_taxcode]["TAXAMOUNT"] += flt(
                item.unit_subtotal * (tax_rate_map.get(str(item_taxcode)) / 100), 2
            )

    vattotals_list = []
    taxes_map = {"1": "A", "2": "B", "3": "C", "4": "D", "5": "E"}
    for key, value in vattotals.items():
        vattotals_list.append({"VATRATE": taxes_map.get(str(key))})
        vattotals_list.append({"NETTAMOUNT": flt(value["NETTAMOUNT"], 2)})
        vattotals_list.append({"TAXAMOUNT": flt(value["TAXAMOUNT"], 2)})
    return vattotals_list
