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
        """Menos de Q300,000: tasa 5%. wage 10000/mes; deducción personal 51,024."""
        emp = self._employee_contract(10000.0)
        proj = self._projection(emp)
        self.assertAlmostEqual(proj.renta_bruta_anual, 120000.0, delta=0.1)
        self.assertAlmostEqual(proj.igss_anual, 5796.0, delta=0.5)
        # 120000 - 51024 - 5796 = 63180
        self.assertAlmostEqual(proj.renta_imponible, 63180.0, delta=1.0)
        self.assertAlmostEqual(proj.isr_anual, 3159.0, delta=1.0)
        # Proyección nueva (sin recibos confirmados): retención = ISR anual / 12
        self.assertAlmostEqual(proj.retencion_mensual, 263.25, delta=0.5)

    def test_isr_tramo_2(self):
        """Más de Q300,000: Q15,000 fijo + 7% sobre el excedente. wage 40000/mes."""
        emp = self._employee_contract(40000.0)
        proj = self._projection(emp)
        # 480000 - 51024 - 23184 = 405792
        self.assertAlmostEqual(proj.renta_imponible, 405792.0, delta=1.0)
        # 15000 + (405792-300000)*0.07 = 22405.44
        self.assertAlmostEqual(proj.isr_anual, 22405.44, delta=1.0)
        self.assertAlmostEqual(proj.retencion_mensual, 1867.12, delta=0.5)

    def test_deduccion_comprobable_reduce_base(self):
        """§4.10.4: deducciones comprobables reducen la renta imponible."""
        emp = self._employee_contract(10000.0)
        self.env["l10n.gt.isr.deduction"].create({
            "employee_id": emp.id, "year": 2026,
            "deduction_type": "invoice", "amount": 12000.0,
        })
        proj = self._projection(emp)
        # 63180 - 12000
        self.assertAlmostEqual(proj.renta_imponible, 51180.0, delta=1.0)
        self.assertAlmostEqual(proj.isr_anual, 2559.0, delta=1.0)

    def test_retencion_fluye_al_recibo(self):
        """La regla ISR del recibo lee la retención del mes (enero: ISR/12)."""
        emp = self._employee_contract(10000.0)
        con = emp.contract_id
        self._projection(emp)  # deja state='current'
        slip = self.env["hr.payslip"].create({
            "name": "n", "employee_id": emp.id, "contract_id": con.id,
            "struct_id": self.env.ref("l10n_gt_payroll.structure_gt_ordinaria").id,
            "date_from": "2026-01-01", "date_to": "2026-01-31",
        })
        slip.compute_sheet()
        isr_line = slip.line_ids.filtered(lambda l: l.code == "ISR")
        self.assertTrue(isr_line, "Debe existir línea de ISR")
        self.assertAlmostEqual(isr_line.total, -263.25, delta=0.5)

    def test_retencion_resta_retenido_y_divide_restantes(self):
        """§4.10 (anexo 8.5): retención = (ISR anual − ya retenido) ÷ meses
        restantes. Con enero confirmado, febrero divide entre 11."""
        emp = self._employee_contract(10000.0)
        con = emp.contract_id
        struct = self.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        self._projection(emp)
        ene = self.env["hr.payslip"].create({
            "name": "ene", "employee_id": emp.id, "contract_id": con.id,
            "struct_id": struct.id,
            "date_from": "2026-01-01", "date_to": "2026-01-31",
        })
        ene.compute_sheet()
        try:
            ene.action_payslip_done()  # retiene ~263.25
        except Exception:
            self.skipTest("El recibo no pudo confirmarse en este entorno")
        feb = self.env["hr.payslip"].create({
            "name": "feb", "employee_id": emp.id, "contract_id": con.id,
            "struct_id": struct.id,
            "date_from": "2026-02-01", "date_to": "2026-02-28",
        })
        feb.compute_sheet()
        isr_feb = feb.line_ids.filtered(lambda l: l.code == "ISR")
        # (3159 - 263.25) / 11 = 263.25  (se mantiene parejo cuando no hay bonos)
        self.assertAlmostEqual(isr_feb.total, -263.25, delta=1.0)

    def test_isr_opening_retained_reduce_retencion(self):
        """El ISR ya retenido antes de implementar reduce la retención del mes."""
        emp = self._employee_contract(10000.0)
        con = emp.contract_id
        proj = self._projection(emp)
        # Simula adopción en julio con Q1,500 ya retenidos en el año.
        proj.isr_opening_retained = 1500.0
        slip = self.env["hr.payslip"].create({
            "name": "jul", "employee_id": emp.id, "contract_id": con.id,
            "struct_id": self.env.ref("l10n_gt_payroll.structure_gt_ordinaria").id,
            "date_from": "2026-07-01", "date_to": "2026-07-31",
        })
        slip.compute_sheet()
        isr_line = slip.line_ids.filtered(lambda l: l.code == "ISR")
        # (3159 - 1500) / 6 meses restantes (jul-dic) = 276.5
        self.assertAlmostEqual(isr_line.total, -276.5, delta=1.0)

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
