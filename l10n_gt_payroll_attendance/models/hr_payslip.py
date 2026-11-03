# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.tools import format_date

# Exceso diario menor a esto no se recomienda (marcar unos minutos antes o
# después de la jornada no es hora extra).
DAILY_TOLERANCE_HOURS = 0.25


class HrPayslip(models.Model):
    """Horas extra detectadas por asistencia, como RECOMENDACIÓN.

    Se calculan día por día contra el horario del CONTRATO del empleado (no con
    el cálculo de horas extra de Odoo, que usa su propia regla y hoy se aprueba
    solo): horas registradas en asistencia − horas que el horario del contrato
    prevé ese día. Nunca se suman al recibo: quien hace la nómina las compara con
    las capturadas y decide."""

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
    l10n_gt_overtime_detail = fields.Html(
        "Detalle por día", compute="_compute_l10n_gt_overtime", sanitize=False)

    def _l10n_gt_overtime_calendar(self):
        self.ensure_one()
        return (self.contract_id.resource_calendar_id
                or self.employee_id.resource_calendar_id
                or self.company_id.resource_calendar_id)

    def _l10n_gt_overtime_by_day(self):
        """{fecha local: (horas registradas, horas del horario)} para los días del
        período con asistencia."""
        self.ensure_one()
        calendar = self._l10n_gt_overtime_calendar()
        if not (self.employee_id and self.date_from and self.date_to and calendar):
            return {}
        tz = pytz.timezone(calendar.tz or self.employee_id.tz or "UTC")
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
        result = {}
        for day, hours in worked.items():
            d1 = tz.localize(datetime.combine(day, time.min))
            planned = calendar.get_work_hours_count(
                d1, d1 + timedelta(days=1), compute_leaves=False)
            result[day] = (hours, planned)
        return result

    @api.depends("employee_id", "contract_id", "date_from", "date_to",
                 "input_line_ids.amount", "input_line_ids.input_type_id")
    def _compute_l10n_gt_overtime(self):
        for slip in self:
            by_day = slip._l10n_gt_overtime_by_day() if slip.id else {}
            rows, total = [], 0.0
            for day in sorted(by_day):
                worked, planned = by_day[day]
                excess = worked - planned
                if excess >= DAILY_TOLERANCE_HOURS:
                    total += excess
                    rows.append((day, worked, planned, excess))
            slip.l10n_gt_overtime_detected = round(total, 2)
            slip.l10n_gt_overtime_detected_days = len(rows)
            slip.l10n_gt_overtime_captured = (
                slip._l10n_gt_input("HE_DIURNA") + slip._l10n_gt_input("HE_NOCTURNA")
                if slip.id else 0.0)
            slip.l10n_gt_overtime_calendar_id = (
                slip._l10n_gt_overtime_calendar() if slip.employee_id else False)
            slip.l10n_gt_overtime_detail = slip._l10n_gt_overtime_html(rows)

    def _l10n_gt_overtime_html(self, rows):
        if not rows:
            return False
        cells = "".join(
            "<tr><td>%s</td><td class='text-end'>%.2f</td><td class='text-end'>%.2f</td>"
            "<td class='text-end'><b>%.2f</b></td></tr>" % (
                format_date(self.env, day, date_format="EEE dd/MM"), worked, planned, excess)
            for day, worked, planned, excess in rows)
        return (
            "<table class='table table-sm o_l10n_gt_overtime'><thead><tr>"
            "<th>Día</th><th class='text-end'>Registradas</th>"
            "<th class='text-end'>Horario</th><th class='text-end'>Extra</th>"
            "</tr></thead><tbody>%s</tbody></table>" % cells)

    def action_l10n_gt_view_attendances(self):
        """Asistencias del empleado en el período, para revisar antes de capturar."""
        self.ensure_one()
        calendar = self._l10n_gt_overtime_calendar()
        tz = pytz.timezone((calendar and calendar.tz) or self.employee_id.tz or "UTC")
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
