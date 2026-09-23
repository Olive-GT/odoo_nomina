# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrPayslip(models.Model):
    """Vacaciones del período, registradas en el propio recibo (bajo el principio
    de 'trabajó todos los días − las excepciones'), en un solo lugar y contra el
    mismo saldo de días del empleado:

    - Días GOZADOS: descanso pagado. No cambian el salario; bajan el saldo.
    - Días PAGADOS (no gozados): se pagan en dinero. Generan la línea VAC del
      recibo (días × sueldo diario promedio), que así llega a la planilla, al
      Libro de Salarios, a IGSS/ISR y a la póliza; también bajan el saldo.

    Ambos se anotan en l10n.gt.vacation.taken al confirmar el recibo (y se
    retiran si se cancela)."""

    _inherit = "hr.payslip"

    l10n_gt_vacation_balance = fields.Float(
        "Saldo de vacaciones disponible",
        compute="_compute_l10n_gt_vacation_balance",
        help="Días de vacaciones pendientes del empleado al cierre del período, "
             "sin contar lo anotado en este mismo recibo.")
    l10n_gt_vacation_days = fields.Float(
        "Días gozados (descanso)",
        help="Días de vacaciones que el trabajador descansó en este período. Admite "
             "medios (0.5) y cuartos (0.25) de día. NO cambian el salario (son "
             "descanso pagado); bajan el saldo de vacaciones al confirmar el recibo.")
    l10n_gt_vacation_paid_days = fields.Float(
        "Días pagados (no gozados)",
        help="Días de vacaciones que se pagan en dinero en lugar de descansarlos. "
             "Generan la línea 'Vacaciones pagadas' (VAC) del recibo = días × "
             "sueldo diario promedio, que se suma al líquido y llega a la planilla, "
             "al Libro de Salarios, a IGSS/ISR y a la póliza; bajan el saldo de "
             "vacaciones al confirmar. Después de cambiarlo, vuelve a pulsar "
             "'Calcular hoja'.")

    # (tipo de registro en l10n.gt.vacation.taken, campo del recibo)
    _L10N_GT_VACATION_KINDS = (
        ("gozadas", "l10n_gt_vacation_days"),
        ("pagadas", "l10n_gt_vacation_paid_days"),
    )

    @api.depends("employee_id", "date_to")
    def _compute_l10n_gt_vacation_balance(self):
        for slip in self:
            if not slip.employee_id or not slip.date_to:
                slip.l10n_gt_vacation_balance = 0.0
                continue
            slip.l10n_gt_vacation_balance = (
                slip.employee_id._l10n_gt_vacation_pending_at(
                    slip.date_to, exclude_payslip=slip))

    @api.onchange("l10n_gt_vacation_days", "l10n_gt_vacation_paid_days")
    def _onchange_l10n_gt_vacation_days(self):
        """Avisa (sin bloquear) si gozados + pagados superan el saldo: en la
        práctica se adelantan vacaciones, pero conviene que quede a la vista."""
        total = ((self.l10n_gt_vacation_days or 0.0)
                 + (self.l10n_gt_vacation_paid_days or 0.0))
        if total > 0 and total > self.l10n_gt_vacation_balance + 1e-6:
            return {"warning": {
                "title": "Vacaciones",
                "message": "Se anotan %.2f días de vacaciones (gozados + pagados) "
                           "pero el saldo disponible del empleado es %.2f. El "
                           "saldo quedará negativo (vacaciones adelantadas)."
                           % (total, self.l10n_gt_vacation_balance),
            }}

    @api.constrains("l10n_gt_vacation_days", "l10n_gt_vacation_paid_days")
    def _check_l10n_gt_vacation_days(self):
        for slip in self:
            if (slip.l10n_gt_vacation_days or 0.0) < 0 or (
                    slip.l10n_gt_vacation_paid_days or 0.0) < 0:
                raise ValidationError(
                    "Los días de vacaciones no pueden ser negativos.")

    def _l10n_gt_vacation_daily_wage(self):
        """Sueldo diario base de las vacaciones pagadas (regla VAC): promedio del
        salario ordinario de los últimos 12 meses × 12 / 365, la misma base que usa
        el pasivo laboral (anexo 8.6: Q276.16 para Q8,000)."""
        self.ensure_one()
        if not self.employee_id or not self.date_to:
            return 0.0
        return self.employee_id._l10n_gt_daily_average(
            self.date_to - timedelta(days=365), self.date_to)

    def _l10n_gt_sync_vacation_taken(self):
        """Crea/actualiza los registros de vacaciones (gozadas y pagadas) ligados a
        este recibo; borra el de un tipo que quedó en cero."""
        self.ensure_one()
        Taken = self.env["l10n.gt.vacation.taken"].sudo()
        for kind, field in self._L10N_GT_VACATION_KINDS:
            existing = Taken.search([
                ("payslip_id", "=", self.id), ("kind", "=", kind)], limit=1)
            days = self[field] or 0.0
            if days > 0:
                vals = {
                    "employee_id": self.employee_id.id,
                    "date_from": self.date_from,
                    "date_to": self.date_to,
                    "days": days,
                    "kind": kind,
                    "payslip_id": self.id,
                }
                if existing:
                    existing.write(vals)
                else:
                    Taken.create(vals)
            elif existing:
                existing.unlink()

    def action_payslip_done(self):
        res = super().action_payslip_done()
        for slip in self:
            slip._l10n_gt_sync_vacation_taken()
        return res

    def action_payslip_cancel(self):
        """Un recibo cancelado no consume vacaciones."""
        res = super().action_payslip_cancel()
        self.env["l10n.gt.vacation.taken"].sudo().search(
            [("payslip_id", "in", self.ids)]).unlink()
        return res
