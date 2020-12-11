frappe.ui.form.on("Sales Invoice", {
    onload: function(frm) {
        frm.trigger("make_vfd_btn")
    },
    refresh: function(frm) {
        frm.trigger("make_vfd_btn")
    },
    vfd_cust_id: function(frm) {
        if (frm.doc.vfd_cust_id.length != 9 && frm.doc.vfd_cust_id_type.startsWith('1')){
            frappe.throw(__("TIN Number is should be 9 numbers only"));
        }
    },
    make_vfd_btn: function(frm){
        if (frm.doc.docstatus == 1 && frm.doc.vfd_status != 'Success' && !frm.doc.is_return){
            frm.add_custom_button(__('Generate VFD'), 
            function() {
                frappe.call({
                    method: "vfd_tz.api.sales_invoice.enqueue_posting_vfd_invoice",
                    args: {
                        invoice_name: frm.doc.name,
                    },
                    callback: function(r) {
                        if(!r.exc) {
                            frm.reload_doc();
                        }
                    }
                }); 
            });               
        }
    },
})