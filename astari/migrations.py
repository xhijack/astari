# your_app/your_app/patches/add_attach_image_field.py
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def after_migrate():
    """
    Tambahkan field Attach Image ke Healthcare Service Unit
    dengan memakai create_custom_field (recommended).
    """

    df = {
        "fieldname": "attach_image",
        "label": "Attach Image",
        "fieldtype": "Attach Image",
        "insert_after": "healthcare_service_unit_name",  # sesuaikan jika perlu
        "read_only": 0,
        "reqd": 0
    }

    # create_custom_field sudah otomatis cek duplikasi,
    # jadi aman dipanggil berkali-kali
    create_custom_field("Healthcare Service Unit", df)

    create_custom_field("Healthcare Practitioner", {
        "fieldname": "full_description",
        "label": "Full Description",
        "fieldtype": "Text Editor",
        "insert_after": "office_phone",  # sesuaikan jika
        "read_only": 0,
        "reqd": 0
    })

    create_custom_field("Appointment Type", {
        "fieldname": "description",
        "label": "Description",
        "fieldtype": "Small Text",
        "insert_after": "default_duration",  # sesuaikan jika perlu
    })

    create_custom_field("Appointment Type", {
        "fieldname": "full_description",
        "label": "Full Description",
        "fieldtype": "Text Editor",
        "insert_after": "description",  # sesuaikan jika perlu
    })

    create_custom_field("Appointment Type", {
        "fieldname": "image",
        "label": "Image",
        "fieldtype": "Attach Image",
        "insert_after": "full_description",  # sesuaikan jika perlu
    })


