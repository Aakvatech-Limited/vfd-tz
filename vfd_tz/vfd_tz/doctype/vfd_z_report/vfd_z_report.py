# Copyright (c) 2021, Aakvatech and contributors
# For license information, please see license.txt

from ast import While
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
    flt,
    nowdate,
    nowtime,
    format_datetime,
    get_date_str,
    add_to_date,
)
from vfd_tz.vfd_tz.api.sales_invoice import get_item_taxcode
from vfd_tz.vfd_tz.doctype.vfd_token.vfd_token import get_token
from vfd_tz.api.xml import xml_to_dic, dict_to_xml
from vfd_tz.api.utils import get_signature
import requests


class VFDZReport(Document):
    def before_insert(self):
        self.set_data()

    def before_submit(self):
        self.update_canceled_invoices()

    def on_submit(self):
        pass

    def set_data(self):
        company, serial = frappe.get_value("VFD Registration", self.vfd_registration, ["company", "serial"])
        if not self.serial:
            self.serial = serial
        z_last_gc = get_z_last_gc(self.serial)
        # self.date is the date of the report
        self.time = "23:59:59"
        self.vfd_gc_previous = z_last_gc
        self.znumber = str(self.date).replace("-", "")
        invoices = get_invoices(company, self.date, self.serial)
        self.dailytotalamount = 0
        if len(invoices) > 0:
            self.vfd_gc_from = z_last_gc + 1
            self.vfd_gc_to = get_invoices_last_gc(company, self.date)
            self.set_invoices(invoices)
            self.dailytotalamount = get_gross_between(
                company, self.serial, self.vfd_gc_from, self.vfd_gc_to
            )
        else:
            self.vfd_gc_from = None
            self.vfd_gc_to = None
        self.set_vat_totals()
        # self.gross = get_gross(company)
        self.gross = get_all_gross(company, self.serial) + self.dailytotalamount
        self.discounts = 0
        for invoice in self.invoices:
            self.discounts += invoice.discount_amount
        self.ticketsfiscal = len(self.invoices)
        canceled_invoices = self.get_canceled_invoices()
        self.ticketsvoid = self.ticketsnonfiscal = len(canceled_invoices)
        self.ticketsvoidtotal = sum(
            invoice["base_rounded_total"] or invoice["base_grand_total"]
            for invoice in canceled_invoices
        )
        self.set_payments()

    def get_canceled_invoices(self):
        company, report_start_date = frappe.get_value(
            "VFD Registration",
            self.vfd_registration,
            ["company", "vfd_z_report_start_date"],
        )
        if not report_start_date:
            frappe.throw(
                _("VFD Z-Report Start Date is not set in VFD Registration {0}").format(
                    self.vfd_registration
                )
            )
        canceled_invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": 2,
                "company": company,
                "vfd_status": ["=", "Not Sent"],
                "vfd_z_report": ["in", [None, "", self.name]],
                "posting_date": ["between", report_start_date, "and", self.date],
            },
            fields=["name", "base_rounded_total", "base_grand_total", "vfd_z_report"],
        )
        return canceled_invoices

    def set_payments(self):
        total_payments = 0
        self.payments = []
        payments_list = frappe.get_all(
            "Sales Invoice Payment",
            filters={"parent": ["in", [invoice.invoice for invoice in self.invoices]]},
            fields=["sum(base_amount) as amount", "mode_of_payment"],
            group_by="mode_of_payment",
        )
        # Prepend the other receipt types as we only do INVOICE in ERPNext
        payment_types = ["CASH", "CHEQUE", "CCARD", "EMONEY"]
        exist_types = [i.pmttype for i in self.payments]
        for type in payment_types:
            if type not in exist_types:
                row = self.append("payments", {})
                row.pmttype = type
                row.pmtamount = 0
        payments_data = {}
        for payment in payments_list:
            total_payments += payment.amount
            vfd_pmttype = frappe.get_value(
                "Mode of Payment", payment.mode_of_payment, "vfd_pmttype"
            )
            if not payments_data.get(vfd_pmttype):
                payments_data.setdefault(vfd_pmttype, payment.amount)
            else:
                payments_data[vfd_pmttype] += payment.amount
        for key, value in payments_data.items():
            row = self.append("payments", {})
            row.pmttype = key
            row.pmtamount = value
        diff_total = self.dailytotalamount - total_payments
        row = self.append("payments", {})
        row.pmttype = "INVOICE"
        row.pmtamount = diff_total or 0

    def set_invoices(self, invoices):
        self.invoices = []
        if len(invoices) == 0:
            return
        for el in invoices:
            row = self.append("invoices", {})
            row.invoice = el.name
            row.vfd_gc = el.vfd_gc
            row.total_taxes_and_charges = el.base_total_taxes_and_charges
            row.base_net_total = el.base_net_total
            row.base_grand_total = el.base_rounded_total or el.base_grand_total
            row.discount_amount = el.base_discount_amount

    def set_vat_totals(self):
        self.vats = []
        invoices_list = []
        for row in self.invoices:
            invoices_list.append(row.invoice)
        items = (
            frappe.get_all(
                "Sales Invoice Item",
                filters={"parent": ["in", invoices_list]},
                fields=["*"],
            )
            or []
        )
        vattotals = get_vattotals(items, self.vrn)
        for el in vattotals:
            row = self.append("vats", {})
            row.nettamount = el.get("nettamount")
            row.taxamount = el.get("taxamount")
            row.vatrate = el.get("vatrate")

    def update_canceled_invoices(self):
        canceled_invoices = self.get_canceled_invoices()
        for invoice in canceled_invoices:
            if not invoice.vfd_z_report:
                frappe.db.set_value(
                    "Sales Invoice", invoice.name, "vfd_z_report", self.name
                )


def get_vattotals(items, vrn):
    vattotals = {}
    taxes_map = {1: "A-18.00", 2: "B-0.00", 3: "C-0.00", 4: "D-0.00", 5: "E-0.00"}
    for key, value in taxes_map.items():
        vattotals.setdefault(key, {"NETTAMOUNT": 0, "TAXAMOUNT": 0})
    for item in items:
        item_taxcode = get_item_taxcode(
            item.item_tax_template, item.item_code, item.parent
        )
        vattotals[item_taxcode]["NETTAMOUNT"] += flt(item.base_net_amount, 2)
        if vrn == "NOT REGISTERED":
            vattotals[item_taxcode]["TAXAMOUNT"] = 0
        else:
            vattotals[item_taxcode]["TAXAMOUNT"] += flt(
                item.base_net_amount * ((18 / 100) if item_taxcode == 1 else 0), 2
            )

    vattotals_list = []
    for key, value in vattotals.items():
        vattotals_list.append(
            {
                "vatrate": taxes_map.get(key),
                "nettamount": flt(value["NETTAMOUNT"], 2),
                "taxamount": flt(value["TAXAMOUNT"], 2),
            }
        )

    return vattotals_list


def get_z_last_gc(serial):
    report_list = frappe.db.sql(
        """
    SELECT MAX(vfd_gc_to) as to_gc
    FROM `tabVFD Z Report`
    WHERE
        serial = '{0}'
        and docstatus = 1
    """.format(
            serial
        ),
        as_dict=True,
    )
    if len(report_list) > 0 and report_list[0].get("to_gc"):
        return report_list[0].get("to_gc")
    else:
        return 0


def get_invoices_last_gc(company, date):
    invoices_list = frappe.db.sql(
        """
    SELECT MAX(vfd_gc) as gc
    FROM `tabSales Invoice`
    WHERE 
        company = '{0}'
        and docstatus = 1
        and vfd_date = DATE('{1}')
    """.format(
            company, date
        ),
        as_dict=True,
    )
    if len(invoices_list) > 0 and invoices_list[0].get("gc"):
        return invoices_list[0].get("gc")
    else:
        return None


def get_invoices(company, date, serial):
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "company": company,
            "docstatus": 1,
            "vfd_date": date,
            "vfd_serial": serial,
        },
        fields=["*"],
        order_by="vfd_gc",
    )
    return invoices


# def get_gross(company):
#     invoices_list = frappe.db.sql(
#         """
#     SELECT SUM(IF(base_rounded_total > 0, base_rounded_total, base_grand_total)) as total
#     FROM `tabSales Invoice`
#     WHERE
#         company = '{0}'
#         and docstatus = 1
#         and vfd_gc > 0
#     """.format(
#             company
#         ),
#         as_dict=True,
#     )
#     return invoices_list[0].get("total")


def get_gross_between(company, serial, start, end):
    invoices_list = frappe.db.sql(
        """
    SELECT SUM(IF(base_rounded_total > 0, base_rounded_total, base_grand_total)) as total
    FROM `tabSales Invoice`
    WHERE 
        company = '{0}'
        and docstatus = 1
        and vfd_serial = '{1}'
        and vfd_gc BETWEEN {2} AND {3}
    """.format(
            company, serial, start or 0, end or 0
        ),
        as_dict=True,
    )
    gross = invoices_list[0].get("total")
    return flt(gross, 2) or 0


def get_all_gross(company, serial):
    # invoices_list = frappe.db.sql(
    #     """
    # SELECT SUM(IF(base_rounded_total > 0, base_rounded_total, base_grand_total)) as total
    # FROM `tabSales Invoice`
    # WHERE
    #     company = '{0}'
    #     and vfd_serial = '{1}'
    #     AND docstatus = 1
    # """.format(
    #         company, serial
    #     ),
    #     as_dict=True,
    # )
    # gross = invoices_list[0].get("total")
    gross = 0
    try:
        last_vfd_z_report = frappe.get_last_doc(
            "VFD Z Report", filters={"serial": serial}
        )
        gross = last_vfd_z_report.gross
    except Exception:
        pass
    return flt(gross, 2) or 0


def zreport_posting(doc):
    if doc.zreport_posting_info:
        return
    registration_doc = frappe.get_doc("VFD Registration", doc.vfd_registration)
    token_data = get_token(registration_doc.company)
    if not token_data.get("cert_serial"):
        frappe.log_error("No certificate serial found", "VFD Z Report posting")
        return
    headers = {
        "Content-Type": "Application/xml",
        "Routing-Key": "vfdzreport",
        "Cert-Serial": token_data["cert_serial"],
        "Authorization": token_data["token"],
    }

    zreport = {
        "DATE": doc.date,
        "TIME": format_datetime(str(doc.time), "HH:mm:ss"),
        "HEADER": {
            "LINE": registration_doc.company_name or " ",
            "LINE": registration_doc.street or " ",
            "LINE": registration_doc.mobile or " ",
            "LINE": registration_doc.city
            or " " + ", " + registration_doc.country
            or " ",
        },
        "VRN": registration_doc.vrn,
        "TIN": registration_doc.tin,
        "TAXOFFICE": registration_doc.taxoffice,
        "REGID": registration_doc.regid,
        "ZNUMBER": doc.znumber,
        "EFDSERIAL": registration_doc.serial,
        "REGISTRATIONDATE": get_date_str(registration_doc.vfd_start_date),
        "USER": registration_doc.uin,
        "SIMIMSI": "WEBAPI",
        "TOTALS": {
            "DAILYTOTALAMOUNT": flt(doc.dailytotalamount, 2),
            "GROSS": flt(doc.gross, 2),
            "CORRECTIONS": doc.corrections,
            "DISCOUNTS": flt(doc.discounts, 2),
            "SURCHARGES": flt(doc.surcharges, 2),
            "TICKETSVOID": doc.ticketsvoid,
            "TICKETSVOIDTOTAL": flt(doc.ticketsvoidtotal, 2),
            "TICKETSFISCAL": doc.ticketsfiscal,
            "TICKETSNONFISCAL": doc.ticketsnonfiscal,
        },
        "VATTOTALS": [],
        "PAYMENTS": [],
        "CHANGES": {"VATCHANGENUM": "0", "HEADCHANGENUM": "0"},
        "ERRORS": [],
        "FWVERSION": "3.0",
        "FWCHECKSUM": "WEBAPI",
    }

    for vat in doc.vats:
        zreport["VATTOTALS"].append(
            {
                "VATRATE": flt(vat.vatrate, 2),
                "NETTAMOUNT": flt(vat.nettamount, 2),
                "TAXAMOUNT": flt(vat.taxamount, 2),
            }
        )

    for payment in doc.payments:
        zreport["PAYMENTS"].append(
            {
                "PMTTYPE": payment.pmttype,
                "PMTAMOUNT": flt(payment.pmtamount, 2),
            }
        )

    zreport_xml = (
        str(dict_to_xml(zreport, "ZREPORT")[39:])
        .replace("<None>", "")
        .replace("</None>", "")
    )

    efdms_data = {
        "ZREPORT": zreport,
        "EFDMSSIGNATURE": get_signature(zreport_xml, registration_doc),
    }

    data = dict_to_xml(efdms_data).replace("<None>", "").replace("</None>", "")
    url = registration_doc.url + "/api/efdmszreport"
    response = requests.request("POST", url, headers=headers, data=data, timeout=5)

    if not response.status_code == 200:
        posting_info_doc = frappe.get_doc(
            {
                "doctype": "VFD Z Report Posting Info",
                "vfd_z_report": doc.name,
                "ackcode": response.status_code,
                "ackmsg": response.text,
                "date": nowdate(),
                "time": nowtime(),
                "req_headers": str(headers),
                "req_data": str(data).encode("utf8"),
            }
        )
        doc.db_set("sent_status", "Failed")
        frappe.db.commit()
        return False

    xmldict = xml_to_dic(response.text)
    zack = xmldict.get("zack")
    posting_info_doc = frappe.get_doc(
        {
            "doctype": "VFD Z Report Posting Info",
            "vfd_z_report": doc.name,
            "ackcode": zack.get("ackcode"),
            "ackmsg": zack.get("ackmsg"),
            "date": zack.get("date"),
            "time": zack.get("time"),
            "znumber": zack.get("znumber"),
            "efdmssignature": xmldict.get("efdmssignature"),
            "req_headers": str(headers),
            "req_data": str(data).encode("utf8"),
        }
    )
    posting_info_doc.flags.ignore_permissions = True
    posting_info_doc.insert(ignore_permissions=True)
    frappe.db.commit()
    if int(posting_info_doc.ackcode) == 0:
        doc.db_set("zreport_posting_info", posting_info_doc.name)
        doc.db_set("sent_status", "Success")
        doc.save()
        frappe.db.commit()
        return True
    else:
        doc.db_set("sent_status", "Failed")
        doc.save()
        frappe.db.commit()
        return False


@frappe.whitelist()
def post(z_report_name):
    doc = frappe.get_doc("VFD Z Report", z_report_name)
    zreport_posting(doc)


def multi_zreport_posting():
    for doc_name in frappe.get_all(
        "VFD Z Report",
        filters={"zreport_posting_info": ""},
        pluck="name",
        order_by="date asc",
    ):
        doc = frappe.get_doc("VFD Z Report", doc_name)
        zreport_posting(doc)


def send_multi_vfd_z_reports():
    vfd_registration_list = frappe.get_all(
        "VFD Registration",
        filters={"r_status": "Active", "send_vfd_z_report": 1},
        pluck="name",
    )
    reports = frappe.get_all(
        "VFD Z Report",
        filters={"docstatus": 1, "sent_status": ["!=", "Success"], "vfd_registration": ["in", vfd_registration_list]},
        order_by="vfd_gc_previous",
        pluck="name",
    )
    for report in reports:
        post(report)


def make_vfd_z_report():
    vfd_registration_list = frappe.get_all(
        "VFD Registration",
        filters={"r_status": "Active"},
        fields=["name", "send_vfd_z_report", "serial", "vrn", "vfd_z_report_start_date"],
    )
    for vfd_registration in vfd_registration_list:
        try:
            last_z_report = frappe.get_last_doc(
                "VFD Z Report", filters={"serial": vfd_registration.serial}
            )
            date = add_to_date(last_z_report.date, days=1)
        except Exception:
            date = vfd_registration.vfd_z_report_start_date
        while str(date) < nowdate():
            vfd_z_report_doc = frappe.new_doc("VFD Z Report")
            vfd_z_report_doc.vfd_registration = vfd_registration.name
            vfd_z_report_doc.serial = vfd_registration.serial
            vfd_z_report_doc.vrn = vfd_registration.vrn
            vfd_z_report_doc.date = date
            vfd_z_report_doc.insert()
            vfd_z_report_doc.submit()
            frappe.db.commit()
            date = add_to_date(date, days=1)
    send_multi_vfd_z_reports()


# def make_specific_vfd_z_report(vfd_registration, date):
#     vfd_registration_doc = frappe.new_doc("VFD Z Report")
#     vfd_registration_doc.vfd_registration = vfd_registration
#     vfd_registration_doc.date = date
#     vfd_registration_doc.insert()
#     vfd_registration_doc.submit()
