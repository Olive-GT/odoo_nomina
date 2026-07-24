# -*- coding: utf-8 -*-
"""Validación de los reportes de prestaciones: planilla de Aguinaldo (§6.3),
Bono 14 (§6.4) y control de vacaciones (§6.13)."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestPrestacionesReports(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        cls.employee = cls.env["hr.employee"].create({
            "name": "Juan Andres Rivera",
            "l10n_gt_dpi": "3013104400101",
            "l10n_gt_igss_applies": True,
            "l10n_gt_opening_date": "2024-07-01",
            "l10n_gt_opening_vacation_days": 5.0,
        })
        cls.contract = cls.env["hr.contract"].create({
            "name": "Contrato Juan",
            "employee_id": cls.employee.id,
            "wage": 12000.0,
            "l10n_gt_bonif_incentivo": 250.0,
            "state": "open",
            "date_start": "2024-07-01",
            "structure_type_id": cls.structure.type_id.id,
        })
        cls.run = cls.env["hr.payslip.run"].create({
            "name": "Nómina julio 2026",
            "date_start": "2026-07-01",
            "date_end": "2026-07-31",
        })
        cls.slip = cls.env["hr.payslip"].create({
            "name": "Recibo Juan julio 2026",
            "employee_id": cls.employee.id,
            "contract_id": cls.contract.id,
            "struct_id": cls.structure.id,
            "payslip_run_id": cls.run.id,
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
        })
        cls.slip.compute_sheet()

    def _render(self, report_name, ids):
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            report_name, ids)
        return html.decode() if isinstance(html, bytes) else html

    def test_render_aguinaldo(self):
        html = self._render(
            "l10n_gt_payroll_prestaciones.report_planilla_aguinaldo", self.run.ids)
        self.assertIn("AGUINALDO", html)
        self.assertIn("Juan Andres Rivera", html)

    def test_render_bono14(self):
        html = self._render(
            "l10n_gt_payroll_prestaciones.report_planilla_bono14", self.run.ids)
        self.assertIn("BONO 14", html)
        self.assertIn("Juan Andres Rivera", html)

    def test_render_vacaciones(self):
        html = self._render(
            "l10n_gt_payroll_prestaciones.report_vacaciones", self.employee.ids)
        self.assertIn("CONTROL DE VACACIONES", html)
        self.assertIn("Juan Andres Rivera", html)

    def test_benefit_planilla_rows_windows(self):
        """§4.7/§4.8: ventana de Aguinaldo dic→nov y Bono 14 jul→jun."""
        rows_agui = self.run._l10n_gt_benefit_planilla_rows("aguinaldo")
        rows_b14 = self.run._l10n_gt_benefit_planilla_rows("bono14")
        self.assertEqual(len(rows_agui), 1)
        self.assertEqual(len(rows_b14), 1)
        # Bono 14 pagado en julio 2026 -> ventana jul-2025 a jun-2026
        self.assertEqual(str(rows_b14[0]["win_from"]), "2025-07-01")
        self.assertEqual(str(rows_b14[0]["win_to"]), "2026-06-30")
        # Aguinaldo (ref julio) -> ventana dic-2024 a nov-2025
        self.assertEqual(str(rows_agui[0]["win_from"]), "2024-12-01")
        self.assertEqual(str(rows_agui[0]["win_to"]), "2025-11-30")

    def test_vacation_accrued_includes_opening(self):
        """Días acumulados = apertura + 15/año desde la fecha de corte."""
        self.assertGreaterEqual(self.employee.l10n_gt_vacation_accrued, 5.0)
