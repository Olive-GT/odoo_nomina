# -*- coding: utf-8 -*-
"""Validación del reporte de Proyección de ISR (§6.7): que renderice y que la
retención mensual sea el ISR anual entre 12."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestIsrReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.vat = "1234567-8"
        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        cls.employee = cls.env["hr.employee"].create({
            "name": "Heidi Vanessa Avila",
            "l10n_gt_nit": "5238619-8",
            "l10n_gt_igss_applies": True,
            "l10n_gt_isr_applies": True,
        })
        cls.contract = cls.env["hr.contract"].create({
            "name": "Contrato Heidi",
            "employee_id": cls.employee.id,
            "wage": 20000.0,
            "l10n_gt_bonif_incentivo": 250.0,
            "state": "open",
            "date_start": "2026-01-01",
            "structure_type_id": cls.structure.type_id.id,
        })
        cls.proj = cls.env["l10n.gt.isr.projection"].create({
            "employee_id": cls.employee.id,
            "year": 2026,
        })
        cls.proj.action_generate()

    def _render(self, report_name, ids):
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            report_name, ids)
        return html.decode() if isinstance(html, bytes) else html

    def test_render_isr(self):
        html = self._render(
            "l10n_gt_payroll_isr.report_isr_projection", self.proj.ids)
        self.assertIn("PROYECCIÓN DE ISR", html)
        self.assertIn("Heidi Vanessa Avila", html)
        self.assertIn("Retención mensual", html)

    def test_retencion_es_isr_entre_12(self):
        self.assertAlmostEqual(
            self.proj.retencion_mensual, self.proj.isr_anual / 12.0, 2)

    def test_lineas_doce_meses(self):
        self.assertEqual(len(self.proj.line_ids), 12)

    def test_deduccion_personal_configurada(self):
        """§4.10: deducción personal sin comprobación (parámetro configurable)."""
        self.assertGreater(self.proj.deduccion_personal, 0.0)
