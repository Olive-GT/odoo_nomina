# -*- coding: utf-8 -*-
from odoo import models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def compute_sheet(self):
        """Antes de calcular las líneas, asegura que exista/actualice la proyección
        de ISR vigente, para que la retención aparezca ya en BORRADOR (no solo al
        confirmar). La proyección estima con el salario del contrato los meses sin
        nómina confirmada, así que da un ISR correcto desde el primer cálculo."""
        for slip in self:
            if slip.employee_id.l10n_gt_isr_applies and slip.date_to:
                self.env["l10n.gt.isr.projection"].sudo()._recompute_for(
                    slip.employee_id, slip.date_to.year
                )
        return super().compute_sheet()

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
                # Efecto de sistema: se ejecuta con privilegios para no exigir
                # que el usuario que confirma tenga permisos GT de escritura.
                self.env["l10n.gt.isr.projection"].sudo()._recompute_for(
                    slip.employee_id, slip.date_to.year
                )
        return res
