# -*- coding: utf-8 -*-
from odoo import models


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    def _l10n_gt_benefit_planilla_rows(self, benefit_type):
        """Filas de la planilla de Aguinaldo (§6.3) o Bono 14 (§6.4): por cada
        empleado del lote, la ventana legal, el salario promedio, el tiempo
        laborado y el monto pagadero (devengado − ya pagado)."""
        self.ensure_one()
        ref = self.date_end or self.date_start
        rows = []
        for emp in self.slip_ids.employee_id:
            w_from, w_to = emp._l10n_gt_benefit_window(benefit_type, ref)
            avg = emp._l10n_gt_average_ordinary(w_from, w_to) if w_from else 0.0
            dias = emp._l10n_gt_worked_days_between(w_from, w_to) if w_from else 0
            rows.append({
                "employee": emp.name,
                "dpi": emp.l10n_gt_dpi or "",
                "ingreso": emp.first_contract_date,
                "win_from": w_from,
                "win_to": w_to,
                "dias": dias,
                "average": avg,
                "amount": emp._l10n_gt_benefit_payable(benefit_type, ref),
            })
        return rows
