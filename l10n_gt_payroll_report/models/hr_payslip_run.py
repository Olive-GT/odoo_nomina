# -*- coding: utf-8 -*-
from odoo import models


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    def _l10n_gt_igss_rows(self):
        """Filas del reporte de IGSS (§6.6): base afecta, cuota laboral y
        patronal por empleado."""
        self.ensure_one()
        rows = []
        for slip in self.slip_ids:
            base = slip._l10n_gt_lines_by_category("GTIGSS", "in")
            laboral = slip._l10n_gt_line("IGSSLAB")
            patronal = slip._l10n_gt_line("IGSSPAT")
            rows.append({
                "employee": slip.employee_id.name,
                "affiliation": slip.employee_id.l10n_gt_igss_affiliation or "",
                "dpi": slip.employee_id.l10n_gt_dpi or "",
                "base": base,
                "laboral": -laboral,
                "patronal": patronal,
                "total": -laboral + patronal,
            })
        return rows

    def _l10n_gt_costos_rows(self):
        """Filas del reporte de costos de personal (§6.8)."""
        self.ensure_one()
        rows = []
        for slip in self.slip_ids:
            base = slip._l10n_gt_lines_by_category("GTIGSS", "in")
            patronal_total = slip._l10n_gt_line("IGSSPAT")
            param = self.env["hr.rule.parameter"]._get_parameter_from_code
            d = slip.date_to
            igss = base * param("l10n_gt_igss_patronal_igss", d)
            irtra = base * param("l10n_gt_irtra", d)
            intecap = base * param("l10n_gt_intecap", d)
            ordinario = slip._l10n_gt_line("SALORD")
            bonif = slip._l10n_gt_line("BONINC")
            he = slip._l10n_gt_line("HEXTD") + slip._l10n_gt_line("HEXTN")
            comis = slip._l10n_gt_line("COMIS")
            rows.append({
                "employee": slip.employee_id.name,
                "ordinario": ordinario,
                "bonif": bonif,
                "he": he,
                "comis": comis,
                "igss_pat": igss,
                "irtra": irtra,
                "intecap": intecap,
                "total": ordinario + bonif + he + comis + patronal_total,
            })
        return rows
