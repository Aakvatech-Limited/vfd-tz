import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
    fields = {
        "Sales Invoice": [
            dict(
                fieldname='vfd_serial',
                label='VFD SERIAL',
                fieldtype='Data',
                insert_after='vfd_gc',
                allow_on_submit=1,
            )
        ],
    }

    create_custom_fields(fields, update=True)