# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslip(models.Model):
    """Registro de vacaciones gozadas desde el propio recibo (bajo el principio de
    'trabajó todos los días − las excepciones'): solo marcas los días de vacaciones
    del período. No reducen el salario (son descanso pagado); bajan el saldo de
    días de vacaciones del empleado."""

    _inherit = "hr.payslip"

    l10n_gt_vacation_days = fields.Float(
        "Días de vacaciones gozados",
        help="Días de vacaciones que el trabajador gozó en este período. Admite "
             "medios (0.5) y cuartos (0.25) de día. NO reducen el salario (son "
             "descanso pagado); bajan el saldo de vacaciones. Se registran al "
             "confirmar el recibo.")

    def _l10n_gt_sync_vacation_taken(self):
        """Crea/actualiza el registro de vacaciones gozadas ligado a este recibo."""
        self.ensure_one()
        Taken = self.env["l10n.gt.vacation.taken"].sudo()
        existing = Taken.search([("payslip_id", "=", self.id)], limit=1)
        if self.l10n_gt_vacation_days and self.l10n_gt_vacation_days > 0:
            vals = {
                "employee_id": self.employee_id.id,
                "date_from": self.date_from,
                "date_to": self.date_to,
                "days": self.l10n_gt_vacation_days,
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
