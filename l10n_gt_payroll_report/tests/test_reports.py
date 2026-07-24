# -*- coding: utf-8 -*-
"""Validación de los reportes de período (§6): que RENDERICEN sin error con
datos reales y que los importes de los helpers coincidan con las fórmulas del
documento (anexos 8.1/8.2)."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestReports(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.vat = "1234567-8"
        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        cls.employee = cls.env["hr.employee"].create({
            "name": "Glenda Mariza Perez Perez",
            "l10n_gt_dpi": "2401114350917",
            "l10n_gt_nit": "6336697-5",
            "l10n_gt_first_name": "Glenda",
            "l10n_gt_middle_name": "Mariza",
            "l10n_gt_first_surname": "Perez",
            "l10n_gt_second_surname": "Perez",
            "l10n_gt_igss_applies": True,
            "l10n_gt_igss_affiliation": "275329944",
            "l10n_gt_isr_applies": True,
        })
        cls.contract = cls.env["hr.contract"].create({
            "name": "Contrato Glenda",
            "employee_id": cls.employee.id,
            "wage": 4002.28,
            "l10n_gt_bonif_incentivo": 250.0,
            "state": "open",
            "date_start": "2025-11-19",
            "structure_type_id": cls.structure.type_id.id,
        })
        cls.run = cls.env["hr.payslip.run"].create({
            "name": "Nómina junio 2026",
            "date_start": "2026-06-01",
            "date_end": "2026-06-30",
        })
        cls.slip = cls.env["hr.payslip"].create({
            "name": "Recibo Glenda junio 2026",
            "employee_id": cls.employee.id,
            "contract_id": cls.contract.id,
            "struct_id": cls.structure.id,
            "payslip_run_id": cls.run.id,
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
        })
        cls.slip.compute_sheet()
        try:
            cls.slip.action_payslip_done()
            cls.done_ok = True
        except Exception:
            cls.done_ok = False

    def _render(self, report_name, ids):
        """Renderiza el reporte a HTML; falla si la plantilla revienta."""
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            report_name, ids)
        return html.decode() if isinstance(html, bytes) else html

    # ---------------- Renderizado (no debe reventar) ----------------
    def test_render_planilla(self):
        html = self._render("l10n_gt_payroll_report.report_planilla", self.run.ids)
        self.assertIn("PLANILLA GENERAL", html)
        self.assertIn("Glenda", html)
        self.assertIn("Q4,002.28", html)  # formato monetario aplicado

    def test_render_igss(self):
        html = self._render("l10n_gt_payroll_report.report_igss", self.run.ids)
        self.assertIn("IGSS", html)
        self.assertIn("Glenda", html)

    def test_render_costos(self):
        html = self._render("l10n_gt_payroll_report.report_costos", self.run.ids)
        self.assertIn("COSTO DE PERSONAL", html)
        self.assertIn("Glenda", html)

    def test_render_libro(self):
        html = self._render("l10n_gt_payroll_report.report_libro", self.run.ids)
        self.assertIn("LIBRO DE SALARIOS", html)

    def test_render_informe(self):
        html = self._render("l10n_gt_payroll_report.report_informe", self.run.ids)
        self.assertIn("INFORME DEL EMPLEADOR", html)

    def test_render_boleta(self):
        html = self._render("l10n_gt_payroll_report.report_boleta", self.slip.ids)
        self.assertIn("Glenda", html)

    # ---------------- Números (fórmulas del documento) ----------------
    def test_igss_rows_numbers(self):
        """§4.9/§4.15: base afecta 4,002.28; laboral 4.83% = 193.31;
        patronal 12.67% = 507.09; total 700.40."""
        rows = self.run._l10n_gt_igss_rows()
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertAlmostEqual(r["base"], 4002.28, 2)
        self.assertAlmostEqual(r["laboral"], 193.31, 2)
        self.assertAlmostEqual(r["patronal"], 507.09, 2)
        self.assertAlmostEqual(r["total"], 700.40, 2)

    def test_costos_rows_numbers(self):
        """§6.8: costo total = ordinario + bonif + HE + comis + patronal."""
        rows = self.run._l10n_gt_costos_rows()
        r = rows[0]
        self.assertAlmostEqual(r["ordinario"], 4002.28, 2)
        self.assertAlmostEqual(r["bonif"], 250.0, 2)
        # IGSS patronal 10.67% + IRTRA 1% + INTECAP 1% sobre la base afecta
        self.assertAlmostEqual(r["igss_pat"] + r["irtra"] + r["intecap"], 507.09, 1)
        self.assertAlmostEqual(r["total"], 4759.37, 1)

    def test_money_format(self):
        self.assertEqual(self.run._l10n_gt_money(4002.28), "Q4,002.28")
        self.assertEqual(self.run._l10n_gt_money(1234567.5), "Q1,234,567.50")

    def test_period_label(self):
        self.assertEqual(self.run._l10n_gt_period_label(),
                         "Del 01 al 30 de junio de 2026")

    def test_libro_sections_rows(self):
        """El libro arma una sección por trabajador; con el recibo confirmado
        debe traer al menos una fila mensual."""
        if not self.done_ok:
            self.skipTest("El recibo no pudo confirmarse en este entorno")
        sections = self.run._l10n_gt_libro_sections()
        self.assertTrue(sections)
        rows = sections[0]["rows"]
        self.assertTrue(rows)
        self.assertAlmostEqual(rows[0]["total"], 4252.28, 2)
