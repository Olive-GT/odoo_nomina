# -*- coding: utf-8 -*-
"""Pruebas de aguinaldo, bono 14 y vacaciones (§4.6, §4.7, §4.8)."""
from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestBenefits(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.struct_type = cls.env.ref("l10n_gt_payroll.structure_type_gt_mensual")

    def _emp(self, wage, date_start):
        emp = self.env["hr.employee"].create({"name": "Prest %s" % date_start})
        self.env["hr.contract"].create({
            "name": "c", "employee_id": emp.id, "wage": wage, "state": "open",
            "date_start": date_start,
            "structure_type_id": self.struct_type.id,
        })
        return emp

    def _run(self, benefit_type, year=2026):
        run = self.env["l10n.gt.benefit.run"].create({
            "benefit_type": benefit_type, "year": year,
        })
        run.action_compute()
        return run

    def test_ventana_aguinaldo(self):
        """§4.7: aguinaldo del 01-dic al 30-nov."""
        run = self._run("aguinaldo")
        self.assertEqual(run.date_from, date(2025, 12, 1))
        self.assertEqual(run.date_to, date(2026, 11, 30))

    def test_ventana_bono14(self):
        """§4.8: bono 14 del 01-jul al 30-jun."""
        run = self._run("bono14")
        self.assertEqual(run.date_from, date(2025, 7, 1))
        self.assertEqual(run.date_to, date(2026, 6, 30))

    def test_aguinaldo_anio_completo(self):
        """Empleado con más de un año: aguinaldo = un salario mensual."""
        emp = self._emp(6000.0, "2023-01-01")
        run = self._run("aguinaldo")
        line = run.line_ids.filtered(lambda l: l.employee_id == emp)
        self.assertTrue(line)
        self.assertAlmostEqual(line.amount, 6000.0, delta=20.0)

    def test_aguinaldo_proporcional(self):
        """§4.7.4: menos de un año -> proporcional al tiempo laborado."""
        emp = self._emp(6000.0, "2026-08-01")
        run = self._run("aguinaldo")
        line = run.line_ids.filtered(lambda l: l.employee_id == emp)
        # 01-ago al 30-nov = 122 días; 6000 * 122/365
        self.assertAlmostEqual(line.amount, 2005.48, delta=2.0)

    def test_vacaciones_acumuladas_a_fecha(self):
        """§4.6: 15 días por año de servicio, a una fecha de corte."""
        emp = self._emp(8400.0, "2025-07-21")
        accrued = emp._l10n_gt_vacation_accrued_at(date(2026, 7, 20))
        self.assertAlmostEqual(accrued, 15.0, delta=0.1)

    def test_sueldo_diario_promedio(self):
        """Base diaria GT para prestaciones = mensual x 12 / 365."""
        emp = self._emp(8400.0, "2025-01-01")
        daily = emp._l10n_gt_daily_average(date(2026, 1, 1), date(2026, 6, 30))
        self.assertAlmostEqual(daily, 276.16, delta=0.1)
