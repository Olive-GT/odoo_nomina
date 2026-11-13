# Asuetos 2026 del sector privado (Código de Trabajo art. 127; traslado Dto. 19-2018
# solo aplica al 30-jun -> lunes 29-jun; CC 5536-2018). Días festivos globales de la
# empresa MRO (id 2). Idempotente.
from datetime import datetime
import pytz
env = env(context=dict(env.context, allowed_company_ids=[2]))
tz = pytz.timezone("America/Guatemala")
ASUETOS = [
    ("2026-01-01", None, "Año Nuevo"),
    ("2026-04-02", None, "Jueves Santo"),
    ("2026-04-03", None, "Viernes Santo"),
    ("2026-04-04", None, "Sábado Santo"),
    ("2026-05-01", None, "Día del Trabajo"),
    ("2026-06-29", None, "Día del Ejército (trasladado del 30 de junio)"),
    ("2026-09-15", None, "Día de la Independencia"),
    ("2026-10-20", None, "Día de la Revolución"),
    ("2026-11-01", None, "Día de Todos los Santos"),
    ("2026-12-24", 12, "Nochebuena (medio día, desde las 12:00)"),
    ("2026-12-25", None, "Navidad"),
    ("2026-12-31", 12, "Fin de año (medio día, desde las 12:00)"),
]
Leave = env["resource.calendar.leaves"]
creados = 0
for fecha, desde, nombre in ASUETOS:
    d = datetime.strptime(fecha, "%Y-%m-%d")
    ini = tz.localize(d.replace(hour=desde or 0)).astimezone(pytz.utc).replace(tzinfo=None)
    fin = tz.localize(d.replace(hour=23, minute=59, second=59)).astimezone(pytz.utc).replace(tzinfo=None)
    if Leave.search_count([("resource_id", "=", False), ("company_id", "=", 2), ("date_from", "=", ini)]):
        continue
    Leave.create({"name": nombre, "date_from": ini, "date_to": fin, "company_id": 2,
                  "calendar_id": False, "time_type": "leave"})
    creados += 1
total = Leave.search_count([("resource_id", "=", False), ("company_id", "=", 2)])
print("ASUETOS creados:", creados, "| total días festivos MRO:", total)
env.cr.commit()
