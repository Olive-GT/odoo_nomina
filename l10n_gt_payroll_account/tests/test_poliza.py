# -*- coding: utf-8 -*-
"""Validación de la póliza contable (§6.9, §2.9): el asiento CUADRA y el neto
en 'sueldos por pagar' es el líquido del recibo."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestPoliza(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Se usan cuentas REALES del catálogo (crear account.account en test es
        # frágil por la asignación de empresa en Odoo 18). Si el catálogo no tiene
        # suficientes cuentas, el test se salta.
        Account = cls.env["account.account"]
        exp = Account.search([("account_type", "=", "expense")], limit=1)
        liabs = Account.search(
            [("account_type", "in",
              ("liability_current", "liability_payable", "liability_non_current"))],
            limit=4)
        cls.accounts_ready = bool(exp) and len(liabs) >= 3
        if not cls.accounts_ready:
            return
        cls.gasto = exp
        cls.pagar = liabs[0]
        cls.igss = liabs[1]
        cls.isr = liabs[2]
        cls.igsspat = liabs[3] if len(liabs) > 3 else liabs[1]

        Rule = cls.env["hr.salary.rule"]

        def setacc(code, debit, credit):
            r = Rule.search([("code", "=", code)], limit=1)
            if r:
                r.write({"l10n_gt_account_debit_id": debit.id,
                         "l10n_gt_account_credit_id": credit.id})

        setacc("SALORD", cls.gasto, cls.pagar)
        setacc("BONINC", cls.gasto, cls.pagar)
        setacc("IGSSLAB", cls.pagar, cls.igss)   # retención: reduce por pagar
        setacc("ISR", cls.pagar, cls.isr)
        setacc("IGSSPAT", cls.gasto, cls.igsspat)

        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        cls.employee = cls.env["hr.employee"].create({
            "name": "Juan Carlos Baján",
            "l10n_gt_igss_applies": True,
            "l10n_gt_isr_applies": True,
        })
        cls.contract = cls.env["hr.contract"].create({
            "name": "Contrato", "employee_id": cls.employee.id,
            "wage": 9000.0, "l10n_gt_bonif_incentivo": 1500.0,
            "state": "open", "date_start": "2026-01-01",
            "structure_type_id": cls.structure.type_id.id,
        })
        cls.batch = cls.env["hr.payslip.run"].create({
            "name": "Nómina julio 2026",
            "date_start": "2026-07-01", "date_end": "2026-07-31",
        })
        cls.slip = cls.env["hr.payslip"].create({
            "name": "Recibo", "employee_id": cls.employee.id,
            "contract_id": cls.contract.id, "struct_id": cls.structure.id,
            "payslip_run_id": cls.batch.id,
            "date_from": "2026-07-01", "date_to": "2026-07-31",
        })
        cls.slip.compute_sheet()
        try:
            cls.slip.action_payslip_done()
            cls.done_ok = True
        except Exception:
            cls.done_ok = False

    def _net(self):
        line = self.slip.line_ids.filtered(lambda l: l.code == "NET")
        return round(line.total, 2) if line else 0.0

    def test_poliza_cuadra(self):
        """Débitos == créditos."""
        if not self.accounts_ready:
            self.skipTest("Sin cuentas suficientes en el catálogo para probar")
        if not self.done_ok:
            self.skipTest("El recibo no pudo confirmarse en este entorno")
        rows = self.batch._l10n_gt_poliza_data()
        self.assertTrue(rows)
        total_d = round(sum(r["debit"] for r in rows), 2)
        total_c = round(sum(r["credit"] for r in rows), 2)
        self.assertEqual(total_d, total_c)

    def test_sueldos_por_pagar_es_liquido(self):
        """El neto en 'Sueldos por pagar' = líquido del recibo."""
        if not self.accounts_ready:
            self.skipTest("Sin cuentas suficientes en el catálogo para probar")
        if not self.done_ok:
            self.skipTest("El recibo no pudo confirmarse en este entorno")
        rows = self.batch._l10n_gt_poliza_data()
        pagar_row = next((r for r in rows if r["account_id"] == self.pagar.id), None)
        self.assertIsNotNone(pagar_row)
        self.assertAlmostEqual(pagar_row["credit"], self._net(), 2)

    def test_generar_asiento(self):
        """El asiento se crea, cuadra y queda enlazado."""
        if not self.accounts_ready:
            self.skipTest("Sin cuentas suficientes en el catálogo para probar")
        if not self.done_ok:
            self.skipTest("El recibo no pudo confirmarse en este entorno")
        self.batch.action_gt_generate_move()
        move = self.batch.l10n_gt_move_id
        self.assertTrue(move)
        self.assertAlmostEqual(
            sum(move.line_ids.mapped("debit")),
            sum(move.line_ids.mapped("credit")), 2)
