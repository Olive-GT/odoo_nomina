# -*- coding: utf-8 -*-
"""Proyección de ISR con ingreso a mitad de año y límites de mes (casos reales
que obligaban a corregir el ISR a mano recibo por recibo)."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestIsrIngreso(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.struct_type = cls.env.ref("l10n_gt_payroll.structure_type_gt_mensual")
        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")

    def _employee(self, wage, date_start):
        emp = self.env["hr.employee"].create({
            "name": "ISR ingreso %s" % date_start, "l10n_gt_isr_applies": True,
            "l10n_gt_igss_applies": True,
        })
        self.env["hr.contract"].create({
            "name": "c", "employee_id": emp.id, "wage": wage, "state": "open",
            "date_start": date_start, "structure_type_id": self.struct_type.id,
        })
        return emp

    def _slip(self, emp, date_from, date_to, done=True):
        slip = self.env["hr.payslip"].create({
            "name": "n", "employee_id": emp.id, "contract_id": emp.contract_id.id,
            "struct_id": self.structure.id, "date_from": date_from, "date_to": date_to,
        })
        slip.compute_sheet()
        if done:
            slip.action_payslip_done()
        return slip

    def _projection(self, emp):
        proj = self.env["l10n.gt.isr.projection"].create({
            "employee_id": emp.id, "year": 2026})
        proj.action_generate()
        return proj

    def test_ingreso_a_mitad_de_anio_no_cuenta_meses_previos(self):
        """Edgar: Q5,500 desde el 29/04. Renta proyectada = 2 días de abril + 8
        meses, por debajo de la deducción personal → ISR 0 (lo que el cliente
        ponía a mano)."""
        emp = self._employee(5500.0, "2026-04-29")
        proj = self._projection(emp)
        meses = {l.month: l.sueldo_afecto for l in proj.line_ids}
        self.assertEqual(meses[1], 0.0)
        self.assertEqual(meses[3], 0.0)
        self.assertAlmostEqual(meses[4], 5500.0 / 30 * 2, places=2)
        self.assertAlmostEqual(meses[5], 5500.0, places=2)
        self.assertAlmostEqual(proj.renta_bruta_anual, 5500.0 * 8 + 5500.0 / 30 * 2, places=2)
        self.assertEqual(proj.isr_anual, 0.0)
        self.assertEqual(proj.retencion_mensual, 0.0)

    def test_ingreso_a_mitad_de_anio_con_isr(self):
        """Erick: Q12,000 desde el 15/07 → 17 días de julio + 5 meses."""
        emp = self._employee(12000.0, "2026-07-15")
        proj = self._projection(emp)
        afecto = 12000.0 / 30 * 17 + 12000.0 * 5
        self.assertAlmostEqual(proj.renta_bruta_anual, afecto, places=2)
        igss = afecto * 0.0483
        imponible = afecto - proj.deduccion_personal - igss
        self.assertAlmostEqual(proj.isr_anual, imponible * 0.05, places=1)

    def test_limite_de_mes_no_duplica_recibos(self):
        """Con recibos de agosto y septiembre confirmados, agosto solo suma el
        suyo (antes el límite inclusivo al día 1 contaba también septiembre), y
        el próximo mes a pagar es octubre con lo retenido acumulado."""
        emp = self._employee(5500.0, "2026-04-29")
        self._projection(emp)
        ago = self._slip(emp, "2026-08-01", "2026-08-31")
        sep = self._slip(emp, "2026-09-01", "2026-09-30")
        proj = self.env["l10n.gt.isr.projection"].search([
            ("employee_id", "=", emp.id), ("year", "=", 2026)])
        meses = {l.month: l.sueldo_afecto for l in proj.line_ids}
        self.assertAlmostEqual(meses[8], 5500.0, places=2)
        self.assertAlmostEqual(meses[9], 5500.0, places=2)
        self.assertEqual(proj._next_month_to_pay(), 10)
        retenido = -sum((ago + sep).line_ids.filtered(lambda l: l.code == "ISR").mapped("total"))
        self.assertAlmostEqual(proj.isr_retenido_ytd, retenido, places=2)
