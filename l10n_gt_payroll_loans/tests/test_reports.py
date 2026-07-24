# -*- coding: utf-8 -*-
"""Validación del reporte de Anticipos (§6.12): render y saldo = entregado −
recuperado."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestAnticiposReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        cls.employee = cls.env["hr.employee"].create({
            "name": "Erick Jose Pelaez",
            "l10n_gt_dpi": "2082151740101",
            "l10n_gt_igss_applies": True,
        })
        cls.contract = cls.env["hr.contract"].create({
            "name": "Contrato Erick",
            "employee_id": cls.employee.id,
            "wage": 21965.0,
            "l10n_gt_bonif_incentivo": 250.0,
            "state": "open",
            "date_start": "2023-02-27",
            "structure_type_id": cls.structure.type_id.id,
        })
        cls.slip = cls.env["hr.payslip"].create({
            "name": "Recibo Erick",
            "employee_id": cls.employee.id,
            "contract_id": cls.contract.id,
            "struct_id": cls.structure.id,
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
        })
        cls.slip.compute_sheet()
        # Entrega Q3,000 y recupera Q1,000 (ambos pagados).
        cls.env["l10n.gt.payslip.payment"].create([
            {"payslip_id": cls.slip.id, "benefit_type": "anticipo_given",
             "name": "Anticipo entregado", "amount": 3000.0, "paid": True},
            {"payslip_id": cls.slip.id, "benefit_type": "anticipo_recover",
             "name": "Recuperación", "amount": 1000.0, "paid": True},
        ])

    def _render(self, report_name, ids):
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            report_name, ids)
        return html.decode() if isinstance(html, bytes) else html

    def test_render_anticipos(self):
        html = self._render(
            "l10n_gt_payroll_loans.report_anticipos", self.employee.ids)
        self.assertIn("ANTICIPOS", html)
        self.assertIn("Erick Jose Pelaez", html)

    def test_advance_summary_saldo(self):
        """§4.11: saldo = entregado − recuperado (no negativo)."""
        s = self.employee._l10n_gt_advance_summary()
        self.assertAlmostEqual(s["given"], 3000.0, 2)
        self.assertAlmostEqual(s["recovered"], 1000.0, 2)
        self.assertAlmostEqual(s["balance"], 2000.0, 2)
