# -*- coding: utf-8 -*-
from odoo import api, fields, models


class L10nGtPayslipPayment(models.Model):
    """Conecta los pagos del Estado de Cuenta con las prestaciones: al elegir un
    tipo de prestación, propone el saldo acumulado por pagar de ese empleado."""

    _inherit = "l10n.gt.payslip.payment"

    _BENEFIT_LIABILITY_FIELD = {
        "aguinaldo": "l10n_gt_liab_aguinaldo",
        "bono14": "l10n_gt_liab_bono14",
        "indemnizacion": "l10n_gt_liab_indemnizacion",
        "vacaciones": "l10n_gt_liab_vacaciones",
    }

    @api.onchange("benefit_type")
    def _l10n_gt_onchange_benefit_type(self):
        """Al marcar la línea como una prestación, propone el concepto y el monto =
        saldo del pasivo laboral por pagar (que ya incluye los saldos de apertura +
        lo devengado − lo pagado). Editable si quieres pagar solo una parte."""
        if not self.benefit_type or self.benefit_type == "salary":
            return
        labels = dict(self._fields["benefit_type"].selection)
        self.name = labels.get(self.benefit_type)
        emp = self.payslip_id.employee_id
        if not emp or self.amount:
            return
        field = self._BENEFIT_LIABILITY_FIELD.get(self.benefit_type)
        if field:
            self.amount = emp[field]
