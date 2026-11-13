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


class HrContract(models.Model):
    _inherit = "hr.contract"

    l10n_gt_overtime_compensates = fields.Boolean(
        "Compensa horas (sin horas extra hasta cumplir)",
        help="Para quien no trabaja algunos días de su jornada (p. ej. estudia los "
             "sábados) y los repone quedándose más tiempo otros días: las horas de "
             "más del período primero reponen los sábados no trabajados, y solo lo "
             "que sobra se recomienda como hora extra.")


class HrPayslip(models.Model):
    """Horas extra y asuetos trabajados detectados por asistencia, como
    RECOMENDACIÓN.

    Se calculan día por día contra el horario del CONTRATO del empleado (no con
    el cálculo de horas extra de Odoo, que usa su propia regla): horas
    registradas en asistencia − horas que el horario prevé ese día. Los asuetos
    son los días festivos configurados en Odoo en los que hubo asistencia.
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
    l10n_gt_holiday_captured = fields.Float(
        "Asuetos en recibo", compute="_compute_l10n_gt_overtime",
        help="Días de asueto trabajado capturados en este recibo.")

    def _l10n_gt_overtime_calendar(self):
        self.ensure_one()
        return (self.contract_id.resource_calendar_id
                or self.employee_id.resource_calendar_id
                or self.company_id.resource_calendar_id)

    def _l10n_gt_overtime_tz(self, calendar):
        return pytz.timezone((calendar and calendar.tz) or self.employee_id.tz or "UTC")

    def _l10n_gt_overtime_by_day(self):
        """{fecha local: (horas registradas, horas del horario)} para los días del
        período con asistencia."""
        self.ensure_one()
        calendar = self._l10n_gt_overtime_calendar()
        if not (self.employee_id and self.date_from and self.date_to and calendar):
            return {}
        tz = self._l10n_gt_overtime_tz(calendar)
        start = tz.localize(datetime.combine(self.date_from, time.min))
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
        return {day: (hours, self._l10n_gt_planned_hours(calendar, tz, day))
                for day, hours in worked.items()}

    def _l10n_gt_planned_hours(self, calendar, tz, day):
        d1 = tz.localize(datetime.combine(day, time.min))
        return calendar.get_work_hours_count(d1, d1 + timedelta(days=1), compute_leaves=False)

    def _l10n_gt_holidays(self):
        """Fechas locales de los días festivos (globales) del período."""
        self.ensure_one()
        calendar = self._l10n_gt_overtime_calendar()
        if not (self.date_from and self.date_to):
            return set()
        tz = self._l10n_gt_overtime_tz(calendar)
        start = tz.localize(datetime.combine(self.date_from, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        stop = tz.localize(datetime.combine(self.date_to + timedelta(days=1), time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        leaves = self.env["resource.calendar.leaves"].sudo().search([
            ("resource_id", "=", False),
            ("date_from", "<", stop), ("date_to", ">", start),
            ("company_id", "in", [self.company_id.id, False]),
            "|", ("calendar_id", "=", False), ("calendar_id", "=", calendar.id if calendar else False),
        ])
        days = set()
        for leave in leaves:
            d = pytz.utc.localize(leave.date_from).astimezone(tz).date()
            last = pytz.utc.localize(leave.date_to - timedelta(seconds=1)).astimezone(tz).date()
            while d <= last:
                if self.date_from <= d <= self.date_to:
                    days.add(d)
                d += timedelta(days=1)
        return days

    def _l10n_gt_study_saturdays(self, by_day):
        """Sábados con horario previsto, sin asistencia, dentro de un bloque de
        trabajo (hubo asistencia el viernes anterior y el domingo siguiente): son
        los sábados que la persona no trabaja y debe reponer."""
        self.ensure_one()
        calendar = self._l10n_gt_overtime_calendar()
        tz = self._l10n_gt_overtime_tz(calendar)
        worked = {d for d, (h, _p) in by_day.items() if h >= MIN_WORKED_HOURS}
        result = []
        d = self.date_from
        while d <= self.date_to:
            if (d.weekday() == 5 and d not in worked
                    and (d - timedelta(days=1)) in worked and (d + timedelta(days=1)) in worked):
                planned = self._l10n_gt_planned_hours(calendar, tz, d)
                if planned:
                    result.append((d, planned))
            d += timedelta(days=1)
        return result

    @api.depends("employee_id", "contract_id", "date_from", "date_to",
                 "contract_id.l10n_gt_overtime_compensates",
                 "input_line_ids.amount", "input_line_ids.input_type_id")
    def _compute_l10n_gt_overtime(self):
        for slip in self:
            by_day = slip._l10n_gt_overtime_by_day() if slip.id else {}
            holidays = slip._l10n_gt_holidays() if slip.id else set()
            rows, total, days = [], 0.0, 0
            if slip.contract_id.l10n_gt_overtime_compensates:
                # Las horas de más primero reponen los sábados no trabajados (y los
                # días cortos); solo lo que sobra es hora extra.
                balance = 0.0
                for day in sorted(by_day):
                    worked, planned = by_day[day]
                    if worked < MIN_WORKED_HOURS:
                        continue
                    diff = worked - planned
                    balance += diff
                    if abs(diff) >= DAILY_TOLERANCE_HOURS:
                        rows.append((day, worked, planned, diff, ""))
                        if diff > 0:
                            days += 1
                for day, planned in slip._l10n_gt_study_saturdays(by_day):
                    balance -= planned
                    rows.append((day, 0.0, planned, -planned, "No trabajado: se repone"))
                rows.sort()
                total = max(balance, 0.0)
            else:
                for day in sorted(by_day):
                    worked, planned = by_day[day]
                    excess = worked - planned
                    if excess >= DAILY_TOLERANCE_HOURS:
                        total += excess
                        days += 1
                        rows.append((day, worked, planned, excess, ""))
            worked_holidays = sorted(
                d for d in holidays if by_day.get(d, (0.0, 0.0))[0] >= MIN_WORKED_HOURS)
            slip.l10n_gt_overtime_detected = round(total, 2)
            slip.l10n_gt_overtime_detected_days = days
            slip.l10n_gt_overtime_captured = (
                slip._l10n_gt_input("HE_DIURNA") + slip._l10n_gt_input("HE_NOCTURNA")
                if slip.id else 0.0)
            slip.l10n_gt_overtime_calendar_id = (
                slip._l10n_gt_overtime_calendar() if slip.employee_id else False)
            slip.l10n_gt_holiday_worked = len(worked_holidays)
            slip.l10n_gt_holiday_worked_dates = ", ".join(
                d.strftime("%d/%m") for d in worked_holidays) or False
            slip.l10n_gt_holiday_captured = slip._l10n_gt_input("ASUETO") if slip.id else 0.0
            slip.l10n_gt_overtime_detail = slip._l10n_gt_overtime_html(
                rows, set(worked_holidays), slip.contract_id.l10n_gt_overtime_compensates, total)

    def _l10n_gt_overtime_html(self, rows, holidays, compensates, total):
        if not rows:
            return False
        cells = "".join(
            "<tr><td>%s%s</td><td class='text-end'>%.2f</td><td class='text-end'>%.2f</td>"
            "<td class='text-end'><b>%+.2f</b></td><td class='text-muted'>%s</td></tr>" % (
                format_date(self.env, day, date_format="EEE dd/MM"),
                " <span class='badge text-bg-warning'>asueto</span>" if day in holidays else "",
                worked, planned, diff, note)
            for day, worked, planned, diff, note in rows)
        foot = ""
        if compensates:
            foot = ("<tfoot><tr><td colspan='3'><b>Saldo del período</b> (compensa horas: "
                    "lo de más primero repone lo no trabajado)</td>"
                    "<td class='text-end'><b>%.2f</b></td><td></td></tr></tfoot>" % total)
        return (
            "<table class='table table-sm o_l10n_gt_overtime'><thead><tr>"
            "<th>Día</th><th class='text-end'>Registradas</th>"
            "<th class='text-end'>Horario</th><th class='text-end'>Diferencia</th><th></th>"
            "</tr></thead><tbody>%s</tbody>%s</table>" % (cells, foot))

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
