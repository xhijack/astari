import datetime
import calendar
import frappe
from frappe.utils import getdate


@frappe.whitelist(allow_guest=True)
def get_locations():
    """
    Kembalikan list objek:
    [
      { "id": "<unit.name>", "name": "<healthcare_service_unit_name>", "address": "...", "phone": "..." },
      ...
    ]
    """
    # Ambil semua Healthcare Service Unit (sesuaikan nama doctype kalau beda)
    units = frappe.get_all(
        "Healthcare Service Unit",
        fields=["name", "healthcare_service_unit_name","attach_image"],
        filters={"is_group": 0}  # hanya unit, bukan grup
    )

    result = []

    for u in units:
        # Cari satu alamat yang terhubung ke Healthcare Service Unit ini (via Dynamic Link)
        addr = frappe.db.sql(
            """
            SELECT a.address_line1, a.address_line2, a.city, a.state, a.country, a.phone
            FROM `tabAddress` a
            JOIN `tabDynamic Link` dl ON dl.parent = a.name
            WHERE dl.link_doctype = %s AND dl.link_name = %s
            ORDER BY a.modified DESC
            LIMIT 1
            """,
            ("Healthcare Service Unit", u.name),
            as_dict=1
        )

        if addr:
            a = addr[0]
            # Gabungkan bagian address yang ada menjadi satu string
            parts = [
                a.get("address_line1") or "",
                a.get("address_line2") or "",
                a.get("city") or "",
                a.get("state") or "",
                a.get("country") or ""
            ]
            address = ", ".join([p.strip() for p in parts if p.strip()])
            phone = a.get("phone") or ""
        else:
            address = ""
            phone = ""

        result.append({
            "id": u.get("name"),
            "name": u.get("healthcare_service_unit_name") or u.get("name"),
            "address": address,
            "phone": phone,
            "photo": u.get("attach_image") or ""
        })

    return result


@frappe.whitelist(allow_guest=True)
def get_services():
    """
    Kembalikan list objek:
    [
      { "id": "<service.name>", "name": "<service_name>", "description": "...", "price": 100000 },
      ...
    ]
    """
    services = frappe.get_all(
        "Appointment Type",
        fields=["name", "default_duration","description","full_description","image"]
    )
    frappe.response["data"] = services
    frappe.response["http_status_code"] = 200

@frappe.whitelist(allow_guest=True)
def get_doctors():
    doctors = frappe.get_all(
        "Healthcare Practitioner",
        fields=["name","practitioner_name","image","full_description"]
    )
    respond = []
    for d in doctors:
        doctor = {
            "id": d.get("name"),
            "name": d.get("practitioner_name") or d.get("name"),
            "photo": d.get("image") or "",
            "full_description": d.get("full_description") or ""
        }
        respond.append(doctor)
    frappe.response["data"] = respond
    frappe.response["http_status_code"] = 200


@frappe.whitelist(allow_guest=True)
def get_schedules(doctor, month, location):
    """
    doctor: string nama dari Healthcare Practitioner
    month: string format "YYYY-MM"
    location: string nama dari Healthcare Service Unit
    returns: list of { "date": "YYYY-MM-DD", "status": "available"/"not_available" }
    """

    # parse month
    try:
        year_str, mm_str = month.split("-")
        year = int(year_str)
        mm = int(mm_str)
    except Exception:
        frappe.throw(f"Invalid month format: {month}. Expected YYYY-MM")

    # find practitioner
    practitioner_name = frappe.db.get_value("Healthcare Practitioner",
                                            {"name": doctor}, "name")
    if not practitioner_name:
        frappe.throw(f"Practitioner '{doctor}' not found")

    # find service unit (location)
    service_unit_name = frappe.db.get_value("Healthcare Service Unit",
                                            {"name": location}, "name")
    if not service_unit_name:
        frappe.throw(f"Healthcare Service Unit '{location}' not found")

    # compute first and last day of month
    first_date = getdate(f"{year}-{mm:02d}-01")
    last_day_num = calendar.monthrange(year, mm)[1]
    last_date = first_date + datetime.timedelta(days=last_day_num - 1)

    # fetch practitioner doc
    practitioner_doc = frappe.get_doc("Healthcare Practitioner", practitioner_name)

    # get schedule entries associated with practitioner + service_unit = location
    schedule_entries = practitioner_doc.get("practitioner_schedules") or []

    # we will filter entries by service_unit == location
    filtered_entries = []
    for entry in schedule_entries:
        if entry.get("service_unit") == service_unit_name:
            # include this entry
            filtered_entries.append(entry)

    result = []
    cur_date = first_date
    while cur_date <= last_date:
        date_str = cur_date.strftime("%Y-%m-%d")
        weekday_name = cur_date.strftime("%A")

        # check if slot defined for this weekday in filtered entries
        slot_defined = False
        for entry in filtered_entries:
            schedule_link = entry.get("schedule")
            if not schedule_link:
                continue
            sched_doc = frappe.get_doc("Practitioner Schedule", schedule_link)
            if sched_doc.get("disabled"):
                continue
            for ts in sched_doc.get("time_slots") or []:
                if ts.get("day") == weekday_name:
                    slot_defined = True
                    break
            if slot_defined:
                break

        if not slot_defined:
            status = "not_available"
        else:
            # count bookings for this practitioner + service_unit on this date
            booked_count = frappe.db.count(
                "Patient Appointment",
                {
                    "practitioner": practitioner_name,
                    "service_unit": service_unit_name,
                    "appointment_date": cur_date,
                    "status": ["not in", ["Cancelled", "Closed"]]
                }
            )

            # default logic: available if none booked; else not
            if booked_count == 0:
                status = "available"
            else:
                status = "not_available"

        result.append({"date": date_str, "status": status})
        cur_date = cur_date + datetime.timedelta(days=1)

    frappe.response["data"] = result
    frappe.response["http_status_code"] = 200


def parse_time_value(val):
    """
    Parses value val which may be:
     - datetime.timedelta
     - datetime.time
     - string "HH:MM" or "HH:MM:SS"
    Returns a datetime.time object.
    """
    if isinstance(val, datetime.timedelta):
        total_secs = val.total_seconds()
        hours = int(total_secs // 3600)
        minutes = int((total_secs % 3600) // 60)
        return datetime.time(hours, minutes)
    elif isinstance(val, datetime.time):
        return val
    else:
        s = str(val)
        try:
            return datetime.datetime.strptime(s, "%H:%M").time()
        except ValueError:
            return datetime.datetime.strptime(s, "%H:%M:%S").time()

@frappe.whitelist(allow_guest=True)
def get_schedule_detail(doctor, date, location):
    """
    doctor: string nama dari Healthcare Practitioner
    date: string format "YYYY-MM-DD"
    location: string nama dari Healthcare Service Unit
    returns: list of {
        "start_time": "HH:MM",
        "end_time":   "HH:MM",
        "status":     "available"/"not_available"
    }
    """
    # parse date
    try:
        target_date = getdate(date)
    except Exception:
        frappe.throw(f"Invalid date format: {date}. Expected YYYY-MM-DD")

    # find practitioner
    practitioner_name = frappe.db.get_value("Healthcare Practitioner",
                                            {"name": doctor}, "name")
    if not practitioner_name:
        frappe.throw(f"Practitioner '{doctor}' not found")

    # find service unit (location)
    service_unit_name = frappe.db.get_value("Healthcare Service Unit",
                                            {"name": location}, "name")
    if not service_unit_name:
        frappe.throw(f"Healthcare Service Unit '{location}' not found")

    weekday_name = target_date.strftime("%A")

    # fetch practitioner doc
    practitioner_doc = frappe.get_doc("Healthcare Practitioner", practitioner_name)

    # filter schedule entries with this service unit
    schedule_entries = practitioner_doc.get("practitioner_schedules") or []
    filtered_entries = [entry for entry in schedule_entries
                        if entry.get("service_unit") == service_unit_name]

    if not filtered_entries:
        # no schedule at this service unit => no slots
        return []

    # gather all time_slots for matching weekday
    slots = []
    for entry in filtered_entries:
        schedule_link = entry.get("schedule")
        if not schedule_link:
            continue
        sched_doc = frappe.get_doc("Practitioner Schedule", schedule_link)
        if sched_doc.get("disabled"):
            continue
        for ts in sched_doc.get("time_slots") or []:
            if ts.get("day") == weekday_name:
                slots.append({
                    "start_time": ts.get("from_time"),
                    "end_time":   ts.get("to_time"),
                })

    if not slots:
        return []

    # fetch appointments for that date + practitioner + service unit
    appointments = frappe.get_all("Patient Appointment",
                                  filters = {
                                    "practitioner": practitioner_name,
                                    "service_unit": service_unit_name,
                                    "appointment_date": target_date,
                                    "status": ["not in", ["Cancelled", "Closed"]]
                                  },
                                  fields = ["appointment_time", "duration"])
    booked_ranges = []
    for ap in appointments:
        ap_time_raw = ap.get("appointment_time")
        slot_start = parse_time_value(ap_time_raw)
        dur = ap.get("duration") or 0
        slot_end_dt = datetime.datetime.combine(target_date, slot_start) + datetime.timedelta(minutes=dur)
        slot_end = slot_end_dt.time()
        booked_ranges.append((slot_start, slot_end))

    def is_slot_available(start_val, end_val):
        start_t = parse_time_value(start_val)
        end_t   = parse_time_value(end_val)
        for bstart, bend in booked_ranges:
            if (start_t < bend and end_t > bstart):
                return False
        return True

    result = []
    for s in slots:
        available = is_slot_available(s["start_time"], s["end_time"])
        # for response: convert times back to "HH:MM" (strip seconds if any)
        st = parse_time_value(s["start_time"]).strftime("%H:%M")
        et = parse_time_value(s["end_time"]).strftime("%H:%M")
        result.append({
            "start_time": st,
            "end_time":   et,
            "status":     "available" if available else "not_available"
        })

    frappe.response["data"] = result
    frappe.response["http_status_code"] = 200

