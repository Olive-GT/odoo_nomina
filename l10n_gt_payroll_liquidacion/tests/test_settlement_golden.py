# -*- coding: utf-8 -*-
"""Caso dorado de liquidación (anexo 8.6: Cristofer del Águila).

Salario Q8,400; ingreso 18-May-2026; baja 17-Jul-2026 (despido); 61 días.
Esperado: Bono 14 y Aguinaldo proporcional Q1,403.84 c/u, vacaciones ~Q692,
indemnización Q1,637.81.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestSettlementGolden(TransactionCase):

    def test_cristofer_liquidacion(self):
        employee = self.env["hr.employee"].create({
            "name": "Cristofer Lizandro del Águila Castillo",
            "l10n_gt_dpi": "1977611940501",
        })
        self.env["hr.contract"].create({
            "name": "Contrato Cristofer",
            "employee_id": employee.id,
            "wage": 8400.0,
            "l10n_gt_bonif_incentivo": 250.0,
            "state": "open",
            "date_start": "2026-05-18",
        })
        settlement = self.env["l10n.gt.settlement"].create({
            "employee_id": employee.id,
            "date_end": "2026-07-17",
            "reason": "despido_injustificado",
        })
        settlement.action_compute()

        self.assertAlmostEqual(settlement.bono14_prop, 1403.84, delta=1.0)
        self.assertAlmostEqual(settlement.aguinaldo_prop, 1403.84, delta=1.0)
        self.assertAlmostEqual(settlement.indemnizacion, 1637.81, delta=2.0)
        self.assertAlmostEqual(settlement.vacaciones, 692.30, delta=3.0)
        self.assertTrue(settlement.has_indemnity)
