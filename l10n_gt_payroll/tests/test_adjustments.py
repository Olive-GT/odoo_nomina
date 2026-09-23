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

    def _rule_id(self, code):
        return self._rule(code).id

    def test_add_bonus_row_writes_input(self):
        """Agregar 'Bonificaciones adicionales' con Total 500 en la tabla guarda la
        entrada BONIF (no un ajuste) y el NET sube 500."""
        net0 = self._line("NET")
        self.slip.write({"line_ids": [(0, 0, {
            "salary_rule_id": self._rule_id("BONIF"), "name": "x", "total": 500.0})]})
        self.assertAlmostEqual(self._line("BONIF"), 500.0, places=2)
        self.assertAlmostEqual(self._line("NET"), net0 + 500.0, places=2)
        self.assertEqual(self.slip._l10n_gt_input("BONIF"), 500.0)
        self.assertFalse(self.slip.l10n_gt_adjustment_ids)

    def test_add_deduction_row_uses_sign(self):
        """Otras deducciones: Total -80 en la tabla → entrada OTRDED = 80."""
        net0 = self._line("NET")
        self.slip.write({"line_ids": [(0, 0, {
            "salary_rule_id": self._rule_id("OTRDED"), "name": "x", "total": -80.0})]})
        self.assertEqual(self.slip._l10n_gt_input("OTRDED"), 80.0)
        self.assertAlmostEqual(self._line("NET"), net0 - 80.0, places=2)

    def test_overtime_hours_in_quantity(self):
        """Horas extra diurnas: agregar con Cantidad 8 → 8 × 6000/240 × 1.5; luego
        editar la Cantidad a 4 recalcula."""
        self.slip.write({"line_ids": [(0, 0, {
            "salary_rule_id": self._rule_id("HEXTD"), "name": "x", "quantity": 8.0})]})
        factor = self.env["hr.rule.parameter"]._get_parameter_from_code(
            "l10n_gt_he_diurna_factor", self.slip.date_to)
        self.assertEqual(self.slip._l10n_gt_input("HE_DIURNA"), 8.0)
        self.assertAlmostEqual(self._line("HEXTD"), 8 * 6000 / 240 * factor, places=2)
        line = self.slip.line_ids.filtered(lambda l: l.code == "HEXTD")
        self.assertTrue(line.l10n_gt_qty_editable)
        self.slip.write({"line_ids": [(1, line.id, {"quantity": 4.0})]})
        self.assertAlmostEqual(self._line("HEXTD"), 4 * 6000 / 240 * factor, places=2)

    def test_delete_row(self):
        """Quitar la fila de una entrada borra el dato; quitar un concepto
        calculado (IGSS) lo fija en 0."""
        self.slip.write({"line_ids": [(0, 0, {
            "salary_rule_id": self._rule_id("BONIF"), "name": "x", "total": 300.0})]})
        bonif = self.slip.line_ids.filtered(lambda l: l.code == "BONIF")
        self.slip.write({"line_ids": [(2, bonif.id)]})
        self.assertEqual(self._line("BONIF"), 0.0)
        self.assertEqual(self.slip._l10n_gt_input("BONIF"), 0.0)
        igss = self.slip.line_ids.filtered(lambda l: l.code == "IGSSLAB")
        self.slip.write({"line_ids": [(2, igss.id)]})
        self.assertEqual(self._line("IGSSLAB"), 0.0)
        self.assertTrue(self.slip.l10n_gt_adjustment_ids)

    def test_subtotal_not_adjustable(self):
        with self.assertRaises(UserError):
            self._edit_in_table("NET", 1.0)

    def test_chatter_logs_adjustment(self):
        before = len(self.slip.message_ids)
        self._adjust("OTRDED", -10.0, note="descuento de uniforme")
        self.assertGreater(len(self.slip.message_ids), before)
        self.assertIn("descuento de uniforme", self.slip.message_ids[0].body)
