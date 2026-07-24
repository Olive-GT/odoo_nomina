# -*- coding: utf-8 -*-
from odoo import models


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    def _l10n_gt_money(self, amount):
        """Formato monetario guatemalteco para reportes: 'Q10,500.00'.
        Mismo criterio que hr.payslip._l10n_gt_money (símbolo de la empresa +
        separador de miles)."""
        symbol = (self.company_id.currency_id.symbol or "Q") if self else "Q"
        try:
            value = float(amount or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        return "%s%s" % (symbol, "{:,.2f}".format(value))

    def _l10n_gt_period_label(self):
        """Etiqueta de período legible: 'Del 01 al 30 de junio de 2026'."""
        self.ensure_one()
        meses = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                 "agosto", "septiembre", "octubre", "noviembre", "diciembre")
        d1, d2 = self.date_start, self.date_end
        if not d1 or not d2:
            return self.name or ""
        if (d1.year, d1.month) == (d2.year, d2.month):
            return "Del %02d al %02d de %s de %d" % (
                d1.day, d2.day, meses[d2.month - 1], d2.year)
        return "Del %02d de %s de %d al %02d de %s de %d" % (
            d1.day, meses[d1.month - 1], d1.year,
            d2.day, meses[d2.month - 1], d2.year)

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
