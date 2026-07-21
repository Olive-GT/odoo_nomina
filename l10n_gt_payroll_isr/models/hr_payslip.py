# -*- coding: utf-8 -*-
from odoo import models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _l10n_gt_isr_retencion(self):
        """Retención mensual de ISR desde la proyección vigente (§4.10).

        La regla ISR únicamente LEE este valor; el cálculo vive en la proyección.
        """
        self.ensure_one()
        if not self.employee_id.l10n_gt_isr_applies:
            return 0.0
        year = self.date_to.year
        proj = self.env["l10n.gt.isr.projection"].search([
            ("employee_id", "=", self.employee_id.id),
            ("year", "=", year),
            ("state", "=", "current"),
        ], limit=1)
        return proj.retencion_mensual if proj else 0.0

    def action_payslip_done(self):
        """Al confirmar la nómina, recalcular la proyección de ISR (§2.8, §4.10.4)."""
        res = super().action_payslip_done()
        for slip in self:
            if slip.employee_id.l10n_gt_isr_applies:
                self.env["l10n.gt.isr.projection"]._recompute_for(
                    slip.employee_id, slip.date_to.year
                )
        return res
