frappe.ui.form.on("Sales Invoice", {
    onload: function (frm) {
        frm.trigger("make_vfd_btn");
    },
    refresh: function (frm) {
        frm.trigger("make_vfd_btn");
    },
    make_vfd_btn: function (frm) {
        if (frm.doc.docstatus == 1 && frm.doc.vfd_status != 'Success' && !frm.doc.is_return) {
            frm.add_custom_button(__('Generate VFD'),
                function () {
                    frappe.call({
                        method: "vfd_tz.api.sales_invoice.enqueue_posting_vfd_invoice",
                        args: {
                            invoice_name: frm.doc.name,
                        },
                        callback: function (r) {
                            if (!r.exc) {
                                frm.reload_doc();
                            }
                        }
                    });
                }
            );
        }
    },
    default_item_discount: function (frm) {
        frm.doc.items.forEach(item => {
            if (item.discount_percentage) {
                frappe.model.set_value(item.doctype, item.name, 'discount_percentage', frm.doc.default_item_discount);
            }
        });
    },
});