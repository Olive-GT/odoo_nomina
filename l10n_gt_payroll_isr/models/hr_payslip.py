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

    def _l10n_gt_isr_retencion(self, afecto_mes=None):
        """Retención de ISR del mes de este recibo (§4.10, anexo 8.5).

        El cálculo vive en la proyección: proyecta la renta afecta anual (real
        acumulada + ordinario a futuro), le resta lo ya retenido en el año y lo
        divide entre los meses restantes. `afecto_mes` es la renta afecta viva
        de ESTE mes (categoría GTIGSS: ordinario + horas extra + comisiones),
        para reflejar un bono del mes en curso aunque el recibo aún no se
        confirme. La regla ISR solo LEE este valor.
        """
        self.ensure_one()
        if not self.employee_id.l10n_gt_isr_applies or not self.date_to:
            return 0.0
        proj = self.env["l10n.gt.isr.projection"].search([
            ("employee_id", "=", self.employee_id.id),
            ("year", "=", self.date_to.year),
            ("state", "=", "current"),
        ], limit=1)
        if not proj:
            return 0.0
        return proj._retention_for_month(self.date_to.month, afecto_mes)

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
