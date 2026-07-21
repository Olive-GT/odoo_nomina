# -*- coding: utf-8 -*-
"""Casos de prueba dorados tomados de los anexos del diseño funcional.

Requiere hr_payroll (Odoo Enterprise) instalado.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestPayslipGolden(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        cls.employee = cls.env["hr.employee"].create({
            "name": "Glenda Mariza Perez Perez",
            "l10n_gt_dpi": "2401114350917",
            "l10n_gt_igss_applies": True,
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

    def _payslip(self):
        slip = self.env["hr.payslip"].create({
            "name": "Nómina junio 2026 - Glenda",
            "employee_id": self.employee.id,
            "contract_id": self.contract.id,
            "struct_id": self.structure.id,
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
        })
        slip.compute_sheet()
        return slip

    def _line(self, slip, code):
        line = slip.line_ids.filtered(lambda l: l.code == code)
        return round(line.total, 2) if line else 0.0

    def test_glenda_junio_2026(self):
        """Anexo 8.1/8.2: sueldo 4,002.28 + bonif 250; IGSS 193.31; líquido 4,058.97."""
        slip = self._payslip()
        self.assertEqual(self._line(slip, "SALORD"), 4002.28)
        self.assertEqual(self._line(slip, "BONINC"), 250.00)
        self.assertEqual(self._line(slip, "GROSS"), 4252.28)
        self.assertEqual(self._line(slip, "IGSSLAB"), -193.31)
        self.assertEqual(self._line(slip, "NET"), 4058.97)
        # IGSS patronal (costo empresa): 4,002.28 x 12.67% = 507.09
        self.assertEqual(self._line(slip, "IGSSPAT"), 507.09)
