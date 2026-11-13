# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.tools import format_date

# Exceso diario menor a esto no se recomienda (marcar unos minutos antes o
# después de la jornada no es hora extra).
DAILY_TOLERANCE_HOURS = 0.25
# Un día con menos horas que esto no cuenta como día trabajado (marcaje suelto).
MIN_WORKED_HOURS = 1.0


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_gt_rest_day_rule = fields.Selection(
        [("sunday", "Domingo"), ("seventh", "7.º día seguido de trabajo")],
        string="Día de descanso semanal (horas extra)", default="sunday", required=True,
        help="Qué día trabajado se considera descanso semanal trabajado, cuyas horas "
             "se recomiendan TODAS como extra (Código de Trabajo arts. 126 y 128):\n"
             "- Domingo: el descanso es el domingo (costumbre general).\n"
             "- 7.º día seguido: para rotaciones (p. ej. 11x3), el 7.º, 14.º… día "
             "consecutivo trabajado.")


class HrContract(models.Model):
    _inherit = "hr.contract"

    l10n_gt_overtime_compensates = fields.Boolean(
        "Compensa horas (sin horas extra hasta cumplir)",
        help="Para quien no trabaja algunos días de su jornada (p. ej. estudia los "
             "sábados) y los repone quedándose más tiempo otros días: las horas de "
             "más del período primero reponen los sábados no trabajados, y solo lo "
             "que sobra se recomienda como hora extra.")


class HrPayslip(models.Model):
    """Horas extra detectadas por asistencia, como RECOMENDACIÓN, con la regla
    general del Código de Trabajo (arts. 121, 126-129):

    - Día normal: lo que pase de la jornada que el horario del CONTRATO prevé.
    - Asueto (día festivo configurado en Odoo): el salario del mes ya lo paga;
      el tiempo trabajado se paga como extraordinario → todas sus horas (en
      medio asueto, lo que pase de la media jornada).
    - Descanso semanal trabajado (domingo, o el 7.º día seguido según la
      empresa) → todas sus horas.
    - Contrato que "compensa horas": las horas de más de los días normales
      primero reponen lo no trabajado (sábados de estudio, días cortos).

    Nunca se suman al recibo: quien hace la nómina compara y decide."""

    _inherit = "hr.payslip"

    l10n_gt_overtime_detected = fields.Float(
        "HE asistencia", compute="_compute_l10n_gt_overtime",
        help="Horas extra detectadas en asistencia contra el horario del contrato "
             "(recomendación; no se suman solas al recibo).")
    l10n_gt_overtime_detected_days = fields.Integer(
        "Días con horas extra", compute="_compute_l10n_gt_overtime")
    l10n_gt_overtime_captured = fields.Float(
        "HE en recibo", compute="_compute_l10n_gt_overtime",
        help="Horas extra (diurnas + nocturnas) capturadas en este recibo.")
    l10n_gt_overtime_calendar_id = fields.Many2one(
        "resource.calendar", string="Horario usado",
        compute="_compute_l10n_gt_overtime")
    l10n_gt_overtime_compensates = fields.Boolean(
        related="contract_id.l10n_gt_overtime_compensates")
    l10n_gt_overtime_detail = fields.Html(
        "Detalle por día", compute="_compute_l10n_gt_overtime", sanitize=False)
    l10n_gt_holiday_worked = fields.Integer(
        "Asuetos asistencia", compute="_compute_l10n_gt_overtime",
        help="Días festivos (configurados en Odoo) con asistencia en el período.")
    l10n_gt_holiday_worked_dates = fields.Char(
        "Asuetos trabajados", compute="_compute_l10n_gt_overtime")
    l10n_gt_rest_worked = fields.Integer(
        "Descansos trabajados", compute="_compute_l10n_gt_overtime",
        help="Días trabajados como 7.º día seguido (descanso semanal trabajado): "
             "todas sus horas se recomiendan como extra.")

    def _l10n_gt_overtime_calendar(self):
        self.ensure_one()
        return (self.contract_id.resource_calendar_id
                or self.employee_id.resource_calendar_id
                or self.company_id.resource_calendar_id)

    def _l10n_gt_overtime_tz(self, calendar):
        return pytz.timezone((calendar and calendar.tz) or self.employee_id.tz or "UTC")

    def _l10n_gt_overtime_by_day(self, date_from=None):
        """{fecha local: horas registradas} desde date_from (por defecto el inicio
        del período) hasta el fin del período."""
        self.ensure_one()
        calendar = self._l10n_gt_overtime_calendar()
        date_from = date_from or self.date_from
        if not (self.employee_id and date_from and self.date_to and calendar):
            return {}
        tz = self._l10n_gt_overtime_tz(calendar)
        start = tz.localize(datetime.combine(date_from, time.min))
        stop = tz.localize(datetime.combine(self.date_to + timedelta(days=1), time.min))
        attendances = self.env["hr.attendance"].sudo().search([
            ("employee_id", "=", self.employee_id.id),
            ("check_in", ">=", start.astimezone(pytz.utc).replace(tzinfo=None)),
            ("check_in", "<", stop.astimezone(pytz.utc).replace(tzinfo=None)),
            ("check_out", "!=", False),
        ])
        worked = defaultdict(float)
        for att in attendances:
            day = pytz.utc.localize(att.check_in).astimezone(tz).date()
            worked[day] += att.worked_hours or 0.0
        return dict(worked)

    def _l10n_gt_overtime_days(self):
        """Días del período con asistencia: [(fecha, registradas, horario, tipo)]
        con tipo 'descanso' (7.º día seguido), 'asueto' o 'normal'. 'horario' son
        las horas que el contrato prevé ese día descontando los asuetos (0 en
        asueto completo)."""
        self.ensure_one()
        calendar = self._l10n_gt_overtime_calendar()
        if not (self.employee_id and self.date_from and self.date_to and calendar):
            return []
        tz = self._l10n_gt_overtime_tz(calendar)
        # Dos semanas atrás para saber en qué día de la racha cae cada fecha.
        worked = self._l10n_gt_overtime_by_day(self.date_from - timedelta(days=13))
        streak, prev, pos = {}, None, 0
        for day in sorted(d for d, h in worked.items() if h >= MIN_WORKED_HOURS):
            pos = pos + 1 if prev and (day - prev).days == 1 else 1
            streak[day], prev = pos, day
        days = []
        for day in sorted(worked):
            if day < self.date_from or worked[day] < MIN_WORKED_HOURS:
                continue
            base = self._l10n_gt_planned_hours(calendar, tz, day)
            planned = self._l10n_gt_planned_hours(calendar, tz, day, leaves=True)
            if self.company_id.l10n_gt_rest_day_rule == "seventh":
                rest = streak.get(day, 0) % 7 == 0
            else:
                rest = day.weekday() == 6
            if rest:
                kind, planned = "descanso", 0.0
            elif planned < base:
                kind = "asueto"
            else:
                kind = "normal"
            days.append((day, worked[day], planned, kind))
        return days

    def _l10n_gt_planned_hours(self, calendar, tz, day, leaves=False):
        """Horas que el horario prevé ese día. Con leaves=True descuenta los días
        festivos (globales) configurados en Odoo."""
        d1 = tz.localize(datetime.combine(day, time.min))
        return calendar.get_work_hours_count(d1, d1 + timedelta(days=1), compute_leaves=leaves)

    def _l10n_gt_study_saturdays(self, worked_days):
        """Sábados con horario previsto, sin asistencia, dentro de un bloque de
        trabajo (hubo asistencia el viernes anterior y el domingo siguiente): son
        los sábados que la persona no trabaja y debe reponer."""
        self.ensure_one()
        calendar = self._l10n_gt_overtime_calendar()
        tz = self._l10n_gt_overtime_tz(calendar)
        result = []
        d = self.date_from
        while d <= self.date_to:
            if (d.weekday() == 5 and d not in worked_days
                    and (d - timedelta(days=1)) in worked_days
                    and (d + timedelta(days=1)) in worked_days):
                planned = self._l10n_gt_planned_hours(calendar, tz, d, leaves=True)
                if planned:
                    result.append((d, planned))
            d += timedelta(days=1)
        return result

    @api.depends("employee_id", "contract_id", "date_from", "date_to",
                 "contract_id.l10n_gt_overtime_compensates",
                 "input_line_ids.amount", "input_line_ids.input_type_id")
    def _compute_l10n_gt_overtime(self):
        notes = {
            "descanso": "Descanso semanal trabajado: todo es extra",
            "asueto": "Asueto: el tiempo trabajado es extra",
        }
        for slip in self:
            days = slip._l10n_gt_overtime_days() if slip.id else []
            compensates = slip.contract_id.l10n_gt_overtime_compensates
            rows, special, balance, normal_extra, n_extra = [], 0.0, 0.0, 0.0, 0
            for day, worked, planned, kind in days:
                diff = worked - planned
                if kind != "normal":
                    # Asueto / descanso trabajado: siempre extraordinario.
                    special += max(diff, 0.0)
                    n_extra += 1
                    rows.append((day, worked, planned, diff, notes[kind], kind))
                elif compensates:
                    balance += diff
                    if abs(diff) >= DAILY_TOLERANCE_HOURS:
                        rows.append((day, worked, planned, diff, "", kind))
                        n_extra += diff > 0
                elif diff >= DAILY_TOLERANCE_HOURS:
                    normal_extra += diff
                    n_extra += 1
                    rows.append((day, worked, planned, diff, "", kind))
            if compensates:
                for day, planned in slip._l10n_gt_study_saturdays({d for d, *_ in days}):
                    balance -= planned
                    rows.append((day, 0.0, planned, -planned, "No trabajado: se repone", "normal"))
                normal_extra = max(balance, 0.0)
            rows.sort()
            total = normal_extra + special
            holidays = [d for d, _w, _p, k in days if k == "asueto"]
            slip.l10n_gt_overtime_detected = round(total, 2)
            slip.l10n_gt_overtime_detected_days = n_extra
            slip.l10n_gt_overtime_captured = (
                slip._l10n_gt_input("HE_DIURNA") + slip._l10n_gt_input("HE_NOCTURNA")
                if slip.id else 0.0)
            slip.l10n_gt_overtime_calendar_id = (
                slip._l10n_gt_overtime_calendar() if slip.employee_id else False)
            slip.l10n_gt_holiday_worked = len(holidays)
            slip.l10n_gt_holiday_worked_dates = ", ".join(
                d.strftime("%d/%m") for d in holidays) or False
            slip.l10n_gt_rest_worked = len([1 for *_x, k in days if k == "descanso"])
            slip.l10n_gt_overtime_detail = slip._l10n_gt_overtime_html(
                rows, compensates, normal_extra, special)

    def _l10n_gt_overtime_html(self, rows, compensates, normal_extra, special):
        if not rows:
            return False
        badges = {"asueto": " <span class='badge text-bg-warning'>asueto</span>",
                  "descanso": " <span class='badge text-bg-info'>descanso</span>"}
        cells = "".join(
            "<tr><td>%s%s</td><td class='text-end'>%.2f</td><td class='text-end'>%.2f</td>"
            "<td class='text-end'><b>%+.2f</b></td><td class='text-muted'>%s</td></tr>" % (
                format_date(self.env, day, date_format="EEE dd/MM"), badges.get(kind, ""),
                worked, planned, diff, note)
            for day, worked, planned, diff, note, kind in rows)
        foot = "<tr><td colspan='3'>Días normales%s</td><td class='text-end'><b>%.2f</b></td><td></td></tr>" % (
            " (compensa horas: lo de más primero repone lo no trabajado)" if compensates else "",
            normal_extra)
        if special:
            foot += ("<tr><td colspan='3'>Asuetos y descansos trabajados</td>"
                     "<td class='text-end'><b>%.2f</b></td><td></td></tr>" % special)
        return (
            "<table class='table table-sm o_l10n_gt_overtime'><thead><tr>"
            "<th>Día</th><th class='text-end'>Registradas</th>"
            "<th class='text-end'>Jornada</th><th class='text-end'>Diferencia</th><th></th>"
            "</tr></thead><tbody>%s</tbody><tfoot>%s</tfoot></table>" % (cells, foot))

    def action_l10n_gt_view_attendances(self):
        """Asistencias del empleado en el período, para revisar antes de capturar."""
        self.ensure_one()
        calendar = self._l10n_gt_overtime_calendar()
        tz = self._l10n_gt_overtime_tz(calendar)
        start = tz.localize(datetime.combine(self.date_from, time.min))
        stop = tz.localize(datetime.combine(self.date_to + timedelta(days=1), time.min))
        return {
            "type": "ir.actions.act_window",
            "name": "Asistencias de %s" % self.employee_id.name,
            "res_model": "hr.attendance",
            "view_mode": "list,form",
            "domain": [
                ("employee_id", "=", self.employee_id.id),
                ("check_in", ">=", start.astimezone(pytz.utc).replace(tzinfo=None)),
                ("check_in", "<", stop.astimezone(pytz.utc).replace(tzinfo=None)),
            ],
            "context": {"create": False},
        }
