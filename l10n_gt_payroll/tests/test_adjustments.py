# -*- coding: utf-8 -*-
"""Ajustes manuales por concepto: se aplican dentro del motor de reglas (el
líquido y las deducciones dependientes se recalculan con el total fijado),
sobreviven al recálculo y solo se editan en borrador / en espera."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestManualAdjustments(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        cls.employee = cls.env["hr.employee"].create({
            "name": "Ajuste Prueba",
            "l10n_gt_igss_applies": True,
            "l10n_gt_isr_applies": False,
        })
        cls.contract = cls.env["hr.contract"].create({
            "name": "Contrato Ajuste",
            "employee_id": cls.employee.id,
            "wage": 6000.0,
            "l10n_gt_bonif_incentivo": 250.0,
            "state": "open",
            "date_start": "2024-01-01",
            "structure_type_id": cls.structure.type_id.id,
        })
        cls.slip = cls.env["hr.payslip"].create({
            "name": "Nómina ajuste",
            "employee_id": cls.employee.id,
            "contract_id": cls.contract.id,
            "struct_id": cls.structure.id,
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
        })
        cls.slip.compute_sheet()

    def _line(self, code):
        return sum(self.slip.line_ids.filtered(lambda l: l.code == code).mapped("total"))

    def _rule(self, code):
        return self.structure.rule_ids.filtered(lambda r: r.code == code)[:1]

    def _adjust(self, code, total, note="ajuste de prueba"):
        return self.env["l10n.gt.payslip.adjustment"].create({
            "payslip_id": self.slip.id,
            "salary_rule_id": self._rule(code).id,
            "total": total,
            "note": note,
        })

    def test_deduction_override_flows_to_net(self):
        """Fijar OTRDED en -100 (regla que sin entrada no aparece) baja el NET en 100."""
        net0 = self._line("NET")
        self.assertEqual(self._line("OTRDED"), 0.0)
        adj = self._adjust("OTRDED", -100.0)
        self.slip.compute_sheet()
        self.assertAlmostEqual(self._line("OTRDED"), -100.0, places=2)
        self.assertAlmostEqual(self._line("NET"), net0 - 100.0, places=2)
        self.assertEqual(adj.computed_total, 0.0)
        line = self.slip.line_ids.filtered(lambda l: l.code == "OTRDED")
        self.assertTrue(line.name.endswith("(ajuste manual)"))

    def test_income_override_recomputes_dependents(self):
        """Fijar el salario ordinario recalcula IGSS, GROSS y NET con el nuevo total."""
        igss_rate = self.env["hr.rule.parameter"]._get_parameter_from_code(
            "l10n_gt_igss_laboral", self.slip.date_to)
        adj = self._adjust("SALORD", 5000.0)
        self.slip.compute_sheet()
        self.assertAlmostEqual(self._line("SALORD"), 5000.0, places=2)
        self.assertAlmostEqual(adj.computed_total, 6000.0, places=2)
        self.assertAlmostEqual(self._line("IGSSLAB"), -5000.0 * igss_rate, places=2)
        self.assertAlmostEqual(
            self._line("NET"), 5000.0 + 250.0 - 5000.0 * igss_rate, places=2)

    def test_override_survives_recompute_and_can_be_removed(self):
        net0 = self._line("NET")
        adj = self._adjust("OTRDED", -50.0)
        self.slip.compute_sheet()
        self.slip.compute_sheet()
        self.assertAlmostEqual(self._line("NET"), net0 - 50.0, places=2)
        adj.unlink()
        self.slip.compute_sheet()
        self.assertAlmostEqual(self._line("NET"), net0, places=2)
        self.assertEqual(self._line("OTRDED"), 0.0)

    def test_one_adjustment_per_rule(self):
        self._adjust("OTRDED", -10.0)
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self._adjust("OTRDED", -20.0)

    def test_locked_when_done(self):
        adj = self._adjust("OTRDED", -10.0)
        self.slip.compute_sheet()
        self.slip.action_payslip_done()
        with self.assertRaises(UserError):
            adj.write({"total": -20.0})
        with self.assertRaises(UserError):
            adj.unlink()
        with self.assertRaises(UserError):
            self._adjust("SALORD", 1.0)

    def _edit_in_table(self, code, total):
        """Simula editar el Total en la tabla del formulario y guardar."""
        line = self.slip.line_ids.filtered(lambda l: l.code == code)
        self.slip.write({"line_ids": [(1, line.id, {"total": total})]})

    def test_table_edit_creates_adjustment_and_recomputes(self):
        """Editar IGSS laboral en la tabla: queda el total manual, el NET se
        recalcula, sobrevive a otro cálculo y la línea se marca."""
        net0 = self._line("NET")
        igss0 = self._line("IGSSLAB")
        self._edit_in_table("IGSSLAB", -100.0)
        self.assertAlmostEqual(self._line("IGSSLAB"), -100.0, places=2)
        self.assertAlmostEqual(self._line("NET"), net0 - igss0 - 100.0, places=2)
        adj = self.slip.l10n_gt_adjustment_ids
        self.assertEqual(len(adj), 1)
        self.assertAlmostEqual(adj.computed_total, igss0, places=2)
        self.slip.compute_sheet()
        self.assertAlmostEqual(self._line("IGSSLAB"), -100.0, places=2)
        line = self.slip.line_ids.filtered(lambda l: l.code == "IGSSLAB")
        self.assertTrue(line.name.endswith("(ajuste manual)"))

    def test_table_edit_back_to_computed_removes_adjustment(self):
        igss0 = self._line("IGSSLAB")
        self._edit_in_table("IGSSLAB", -100.0)
        self._edit_in_table("IGSSLAB", igss0)
        self.assertFalse(self.slip.l10n_gt_adjustment_ids)
        self.assertAlmostEqual(self._line("IGSSLAB"), igss0, places=2)

    def test_history_delete_recomputes(self):
        net0 = self._line("NET")
        self._edit_in_table("SALORD", 5000.0)
        adj = self.slip.l10n_gt_adjustment_ids
        self.slip.write({"l10n_gt_adjustment_ids": [(2, adj.id)]})
        self.assertFalse(self.slip.l10n_gt_adjustment_ids)
        self.assertAlmostEqual(self._line("NET"), net0, places=2)

    def test_subtotal_not_adjustable(self):
        with self.assertRaises(UserError):
            self._edit_in_table("NET", 1.0)

    def test_chatter_logs_adjustment(self):
        before = len(self.slip.message_ids)
        self._adjust("OTRDED", -10.0, note="descuento de uniforme")
        self.assertGreater(len(self.slip.message_ids), before)
        self.assertIn("descuento de uniforme", self.slip.message_ids[0].body)
