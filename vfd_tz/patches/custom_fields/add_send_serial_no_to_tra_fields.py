from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    fields = {
        "Sales Invoice": [
            {
                "fieldname": "send_serial_no_to_tra",
                "label": "Send Serial No to TRA (Replace Item Description)",
                "fieldtype": "Check",
                "insert_after": "vfd_z_report",
            }
        ],
    }

    create_custom_fields(fields, update=True)
