# -*- coding: utf-8 -*-
"""Estado de cuenta: se calcula solo, la programación de pagos nace al confirmar
y las quincenas se marcan pagadas desde el lote para todos los recibos."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestEstadoCuentaLote(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        cls.batch = cls.env["hr.payslip.run"].create({
            "name": "Lote prueba", "date_start": "2026-06-01",
            "date_end": "2026-06-30"})
        cls.slips = cls.env["hr.payslip"]
        for i in range(3):
            emp = cls.env["hr.employee"].create({
                "name": "Empleado %d" % i, "l10n_gt_igss_applies": True})
            contract = cls.env["hr.contract"].create({
                "name": "Contrato %d" % i, "employee_id": emp.id, "wage": 6000.0,
                "l10n_gt_bonif_incentivo": 250.0, "state": "open",
                "date_start": "2025-01-01", "l10n_gt_payment_frequency": "biweekly",
                "structure_type_id": cls.structure.type_id.id,
            })
            cls.slips |= cls.env["hr.payslip"].create({
                "name": "Recibo %d" % i, "employee_id": emp.id,
                "contract_id": contract.id, "struct_id": cls.structure.id,
                "payslip_run_id": cls.batch.id,
                "date_from": "2026-06-01", "date_to": "2026-06-30",
            })
        cls.slips.compute_sheet()

    def test_estado_cuenta_se_calcula(self):
        slip = self.slips[0]
        net = sum(slip.line_ids.filtered(lambda l: l.code == "NET").mapped("total"))
        self.assertGreater(net, 0)
        self.assertAlmostEqual(slip.l10n_gt_net_amount, net, places=2)
        self.assertEqual(slip.l10n_gt_payment_state, "none")
        self.assertAlmostEqual(slip.l10n_gt_pending_amount, net, places=2)

    def test_confirmar_lote_programa_y_pagar_quincenas(self):
        self.batch.action_gt_compute()
        self.batch.action_gt_confirm()
        self.assertTrue(all(s.state == "done" for s in self.slips))
        # La programación nace sola al confirmar: dos quincenas por recibo.
        for s in self.slips:
            salary = s.l10n_gt_payment_ids.filtered(lambda p: p.benefit_type == "salary")
            self.assertEqual(len(salary), 2)
            self.assertFalse(any(salary.mapped("paid")))
        self.assertEqual(self.batch.l10n_gt_no_schedule_count, 0)
        self.assertEqual(self.batch.l10n_gt_q1_pending_count, 3)
        # 1ª quincena pagada para los 3 de una vez.
        self.batch.action_gt_pay_quincena_1()
        self.batch.invalidate_recordset()
        self.assertEqual(self.batch.l10n_gt_q1_pending_count, 0)
        self.assertEqual(self.batch.l10n_gt_q2_pending_count, 3)
        for s in self.slips:
            self.assertEqual(s.l10n_gt_payment_state, "partial")
        with self.assertRaises(UserError):
            self.batch.action_gt_pay_quincena_1()
        # 2ª quincena: todo pagado.
        self.batch.action_gt_pay_quincena_2()
        for s in self.slips:
            self.assertEqual(s.l10n_gt_payment_state, "paid")
            self.assertAlmostEqual(s.l10n_gt_pending_amount, 0.0, places=2)

    def test_validate_estandar_equivale_a_confirmar(self):
        """El 'Validar' estándar del lote recorre el flujo GT (un solo camino)."""
        self.batch.action_validate()
        self.assertEqual(self.batch.l10n_gt_state, "confirmed")
        self.assertTrue(all(s.state == "done" for s in self.slips))
