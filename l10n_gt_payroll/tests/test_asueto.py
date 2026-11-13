# -*- coding: utf-8 -*-
"""Asueto trabajado: días × salario diario (mensual / 30) × factor, afecto a IGSS,
capturado en la tabla del recibo con los días en Cantidad."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestAsueto(TransactionCase):

    def test_asueto_desde_la_tabla(self):
        structure = self.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        emp = self.env["hr.employee"].create({"name": "Asueto", "l10n_gt_igss_applies": True,
            "l10n_gt_isr_applies": False})
        contract = self.env["hr.contract"].create({
            "name": "c", "employee_id": emp.id, "wage": 4500.0,
            "l10n_gt_bonif_incentivo": 250.0, "state": "open", "date_start": "2026-01-01",
            "structure_type_id": structure.type_id.id})
        slip = self.env["hr.payslip"].create({
            "name": "n", "employee_id": emp.id, "contract_id": contract.id,
            "struct_id": structure.id, "date_from": "2026-10-01", "date_to": "2026-10-31"})
        slip.compute_sheet()
        net0 = sum(slip.line_ids.filtered(lambda l: l.code == "NET").mapped("total"))
        rule = structure.rule_ids.filtered(lambda r: r.code == "ASUETO")
        self.assertTrue(rule)
        self.assertIn("ASUETO", structure.input_line_type_ids.mapped("code"))
        slip.write({"line_ids": [(0, 0, {"salary_rule_id": rule.id, "name": "x", "quantity": 1.0})]})
        line = slip.line_ids.filtered(lambda l: l.code == "ASUETO")
        self.assertAlmostEqual(line.total, 150.0, places=2)  # 4500 / 30
        rate = self.env["hr.rule.parameter"]._get_parameter_from_code(
            "l10n_gt_igss_laboral", slip.date_to)
        net = sum(slip.line_ids.filtered(lambda l: l.code == "NET").mapped("total"))
        self.assertAlmostEqual(net - net0, 150.0 * (1 - rate), delta=0.01)  # IGSS redondeado a centavos
