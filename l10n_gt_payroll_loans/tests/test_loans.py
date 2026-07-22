# -*- coding: utf-8 -*-
"""Pruebas de préstamos y anticipos (§4.11, §4.12)."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestLoans(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.struct_type = cls.env.ref("l10n_gt_payroll.structure_type_gt_mensual")
        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        cls.emp = cls.env["hr.employee"].create({
            "name": "Prestamo", "l10n_gt_igss_applies": True,
            "l10n_gt_isr_applies": False,
        })
        cls.con = cls.env["hr.contract"].create({
            "name": "c", "employee_id": cls.emp.id, "wage": 6000.0,
            "state": "open", "date_start": "2024-01-01",
            "structure_type_id": cls.struct_type.id,
        })

    def _loan(self, amount, installments, loan_type="loan",
              date_grant="2026-05-01"):
        loan = self.env["l10n.gt.loan"].create({
            "employee_id": self.emp.id, "loan_type": loan_type,
            "amount": amount, "installments": installments,
            "date_grant": date_grant,
        })
        loan.action_confirm()
        return loan

    def test_plan_de_cuotas_iguales(self):
        """§4.12: plan de cuotas iguales que suman el monto original."""
        loan = self._loan(1200.0, 12)
        self.assertEqual(len(loan.line_ids), 12)
        self.assertEqual(round(loan.line_ids[0].amount, 2), 100.00)
        self.assertAlmostEqual(sum(loan.line_ids.mapped("amount")), 1200.0, delta=0.01)
        self.assertEqual(loan.state, "active")
        self.assertEqual(loan.balance, 1200.0)

    def test_descuento_prestamo_en_recibo(self):
        """La cuota vigente se descuenta en la nómina del período (§4.12.2)."""
        self._loan(1200.0, 12)  # cuota 100, 1a vence 2026-06-01
        slip = self._payslip()
        prest = slip.line_ids.filtered(lambda l: l.code == "PREST")
        self.assertEqual(round(prest.total, 2), -100.00)

    def test_anticipo_en_recibo(self):
        """§4.11: el anticipo se descuenta como deducción."""
        self._loan(500.0, 1, loan_type="advance")  # cuota única 500, vence 06-01
        slip = self._payslip()
        antic = slip.line_ids.filtered(lambda l: l.code == "ANTIC")
        self.assertEqual(round(antic.total, 2), -500.00)

    def test_saldo_se_actualiza_al_confirmar(self):
        """§4.12.4: al confirmar el recibo, la cuota queda pagada y baja el saldo."""
        loan = self._loan(1200.0, 12)
        slip = self._payslip()
        slip.action_payslip_done()
        self.assertEqual(loan.balance, 1100.0)
        self.assertEqual(
            len(loan.line_ids.filtered(lambda l: l.state == "paid")), 1)

    def _payslip(self):
        slip = self.env["hr.payslip"].create({
            "name": "n", "employee_id": self.emp.id, "contract_id": self.con.id,
            "struct_id": self.structure.id,
            "date_from": "2026-06-01", "date_to": "2026-06-30",
        })
        slip.compute_sheet()
        return slip
