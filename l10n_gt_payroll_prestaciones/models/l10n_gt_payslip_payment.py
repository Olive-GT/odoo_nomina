# -*- coding: utf-8 -*-
from odoo import api, models


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
        pasivo acumulado por pagar del empleado (editable)."""
        if not self.benefit_type or self.benefit_type == "salary":
            return
        labels = dict(self._fields["benefit_type"].selection)
        self.name = labels.get(self.benefit_type)
        emp = self.payslip_id.employee_id
        field = self._BENEFIT_LIABILITY_FIELD.get(self.benefit_type)
        if emp and field and not self.amount:
            self.amount = emp[field]
