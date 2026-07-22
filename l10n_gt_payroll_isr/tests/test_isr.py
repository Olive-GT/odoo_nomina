# -*- coding: utf-8 -*-
"""Pruebas de la proyección de ISR asalariados (§4.10)."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestIsr(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.struct_type = cls.env.ref(
            "l10n_gt_payroll.structure_type_gt_mensual")

    def _employee_contract(self, wage, isr=True):
        emp = self.env["hr.employee"].create({
            "name": "ISR %s" % wage, "l10n_gt_isr_applies": isr,
            "l10n_gt_igss_applies": True,
        })
        self.env["hr.contract"].create({
            "name": "c", "employee_id": emp.id, "wage": wage, "state": "open",
            "date_start": "2025-01-01",
            "structure_type_id": self.struct_type.id,
        })
        return emp

    def _projection(self, emp, year=2026):
        proj = self.env["l10n.gt.isr.projection"].create({
            "employee_id": emp.id, "year": year,
        })
        proj.action_generate()
        return proj

    def test_isr_tramo_1(self):
        """Menos de Q300,000: tasa 5%. wage 10000/mes."""
        emp = self._employee_contract(10000.0)
        proj = self._projection(emp)
        self.assertAlmostEqual(proj.renta_bruta_anual, 120000.0, delta=0.1)
        self.assertAlmostEqual(proj.igss_anual, 5796.0, delta=0.5)
        self.assertAlmostEqual(proj.renta_imponible, 66204.0, delta=1.0)
        self.assertAlmostEqual(proj.isr_anual, 3310.20, delta=1.0)
        self.assertAlmostEqual(proj.retencion_mensual, 275.85, delta=0.5)

    def test_isr_tramo_2(self):
        """Más de Q300,000: Q15,000 fijo + 7% sobre el excedente. wage 40000/mes."""
        emp = self._employee_contract(40000.0)
        proj = self._projection(emp)
        self.assertAlmostEqual(proj.renta_imponible, 408816.0, delta=1.0)
        self.assertAlmostEqual(proj.isr_anual, 22617.12, delta=1.0)
        self.assertAlmostEqual(proj.retencion_mensual, 1884.76, delta=0.5)

    def test_deduccion_comprobable_reduce_base(self):
        """§4.10.4: deducciones comprobables reducen la renta imponible."""
        emp = self._employee_contract(10000.0)
        self.env["l10n.gt.isr.deduction"].create({
            "employee_id": emp.id, "year": 2026,
            "deduction_type": "invoice", "amount": 12000.0,
        })
        proj = self._projection(emp)
        # 66204 - 12000
        self.assertAlmostEqual(proj.renta_imponible, 54204.0, delta=1.0)
        self.assertAlmostEqual(proj.isr_anual, 2710.20, delta=1.0)

    def test_retencion_fluye_al_recibo(self):
        """La regla ISR del recibo lee la retención de la proyección vigente."""
        emp = self._employee_contract(10000.0)
        con = emp.contract_id
        self._projection(emp)  # deja state='current'
        slip = self.env["hr.payslip"].create({
            "name": "n", "employee_id": emp.id, "contract_id": con.id,
            "struct_id": self.env.ref("l10n_gt_payroll.structure_gt_ordinaria").id,
            "date_from": "2026-06-01", "date_to": "2026-06-30",
        })
        slip.compute_sheet()
        isr_line = slip.line_ids.filtered(lambda l: l.code == "ISR")
        self.assertTrue(isr_line, "Debe existir línea de ISR")
        self.assertAlmostEqual(isr_line.total, -275.85, delta=0.5)

    def test_no_sujeto_isr_sin_retencion(self):
        """Empleado no sujeto a ISR: sin retención en el recibo."""
        emp = self._employee_contract(10000.0, isr=False)
        con = emp.contract_id
        # incluso con proyección, el recibo no retiene
        self.env["l10n.gt.isr.projection"].create({
            "employee_id": emp.id, "year": 2026,
        }).action_generate()
        slip = self.env["hr.payslip"].create({
            "name": "n", "employee_id": emp.id, "contract_id": con.id,
            "struct_id": self.env.ref("l10n_gt_payroll.structure_gt_ordinaria").id,
            "date_from": "2026-06-01", "date_to": "2026-06-30",
        })
        slip.compute_sheet()
        isr_line = slip.line_ids.filtered(lambda l: l.code == "ISR")
        self.assertFalse(isr_line, "No debe retener ISR a un no sujeto")
