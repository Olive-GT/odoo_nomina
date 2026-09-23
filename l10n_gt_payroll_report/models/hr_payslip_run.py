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

    def _l10n_gt_libro_sections(self):
        """Datos del Libro de Salarios (§6.14, anexo 8.3): una sección por
        empleado con su identificación y las filas mensuales (recibos 'done'
        del mismo año del lote, en orden). El libro es histórico y por
        trabajador; el lote define el año a consultar."""
        self.ensure_one()
        year = (self.date_end or self.date_start).year
        meses = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                 "agosto", "septiembre", "octubre", "noviembre", "diciembre")
        Payslip = self.env["hr.payslip"]
        sections = []
        for emp in self.slip_ids.employee_id:
            slips = Payslip.search([
                ("employee_id", "=", emp.id),
                ("state", "in", ("done", "paid")),
                ("date_to", ">=", "%d-01-01" % year),
                ("date_to", "<=", "%d-12-31" % year),
            ], order="date_from")
            rows = []
            for i, s in enumerate(slips, start=1):
                d1, d2 = s.date_from, s.date_to
                periodo = "%02d al %02d/%02d/%d" % (
                    d1.day, d2.day, d2.month, d2.year) if d1 and d2 else (s.name or "")
                ordinario = s._l10n_gt_line("SALORD")
                extra = s._l10n_gt_line("HEXTD") + s._l10n_gt_line("HEXTN")
                comis = s._l10n_gt_line("COMIS")
                vac = s._l10n_gt_line("VAC")
                gross = s._l10n_gt_line("GROSS")
                igss = -s._l10n_gt_line("IGSSLAB")
                isr = -s._l10n_gt_line("ISR")
                ded_total = s._l10n_gt_lines_by_category("DED", "out")
                rows.append({
                    "n": i,
                    "periodo": periodo,
                    "wage": s.contract_id.wage,
                    "dias": s._l10n_gt_worked_days(),
                    "extra_h": extra,
                    "ordinario": ordinario,
                    "extraordinario": extra,
                    # Las vacaciones pagadas tienen su propia columna: fuera de 'otros'.
                    "otros": comis + max(0.0, gross - ordinario - s._l10n_gt_line("BONINC") - extra - comis - vac),
                    "vacaciones": vac,
                    "total": gross,
                    "igss": igss,
                    "isr": isr,
                    "otras_ded": ded_total - igss - isr,
                    "ded_total": ded_total,
                    "bonif_inc": s._l10n_gt_line("BONINC"),
                    "liquido": s._l10n_gt_line("NET"),
                })
            sections.append({
                "employee": emp,
                "rows": rows,
                "year": year,
            })
        return sections

    def _l10n_gt_informe_rows(self):
        """Datos del Informe del Empleador (§6.15, anexo 8.4): identificación +
        montos anuales pagados por empleado (año del lote)."""
        self.ensure_one()
        year = (self.date_end or self.date_start).year
        Payslip = self.env["hr.payslip"]
        rows = []
        for emp in self.slip_ids.employee_id:
            slips = Payslip.search([
                ("employee_id", "=", emp.id),
                ("state", "in", ("done", "paid")),
                ("date_to", ">=", "%d-01-01" % year),
                ("date_to", "<=", "%d-12-31" % year),
            ])
            sal_anual = he_anual = comis = dias = bonif_adic = 0.0
            benef = {"aguinaldo": 0.0, "bono14": 0.0,
                     "vacaciones": 0.0, "indemnizacion": 0.0}
            for s in slips:
                sal_anual += s._l10n_gt_line("SALORD")
                he_anual += s._l10n_gt_line("HEXTD") + s._l10n_gt_line("HEXTN")
                comis += s._l10n_gt_line("COMIS")
                dias += s._l10n_gt_worked_days()
                bonif_adic += max(0.0, s._l10n_gt_line("BONINC") - 250.0)
                # Vacaciones pagadas en el recibo (regla VAC) + las pagadas como
                # prestación del Estado de Cuenta (finiquito).
                benef["vacaciones"] += s._l10n_gt_line("VAC")
                for p in s.l10n_gt_payment_ids:
                    if p.benefit_type in benef and p.paid:
                        benef[p.benefit_type] += p.amount
            rows.append({
                "employee": emp,
                "sal_mensual": emp.contract_id.wage if emp.contract_id else 0.0,
                "sal_anual": sal_anual,
                "he_anual": he_anual,
                "comisiones": comis,
                "dias": dias,
                "bonif_adicional": bonif_adic,
                "aguinaldo": benef["aguinaldo"],
                "bono14": benef["bono14"],
                "vacaciones": benef["vacaciones"],
                "indemnizacion": benef["indemnizacion"],
            })
        return rows

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
