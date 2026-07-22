# -*- coding: utf-8 -*-
"""Pruebas profundas de cálculo de nómina ordinaria (capítulo 4)."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestPayrollDeep(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        cls.struct_type = cls.structure.type_id

    def _employee(self, name="Empleado Prueba", igss=True, isr=False):
        return self.env["hr.employee"].create({
            "name": name,
            "l10n_gt_igss_applies": igss,
            "l10n_gt_isr_applies": isr,
        })

    def _contract(self, employee, wage, date_start="2024-01-01",
                  date_end=False, state="open", bonif=250.0):
        return self.env["hr.contract"].create({
            "name": "Contrato %s" % employee.name,
            "employee_id": employee.id,
            "wage": wage,
            "l10n_gt_bonif_incentivo": bonif,
            "state": state,
            "date_start": date_start,
            "date_end": date_end,
            "structure_type_id": self.struct_type.id,
        })

    def _payslip(self, employee, contract, inputs=None,
                 date_from="2026-06-01", date_to="2026-06-30"):
        input_lines = []
        for code, amount in (inputs or {}).items():
            itype = self.env["hr.payslip.input.type"].search(
                [("code", "=", code)], limit=1)
            input_lines.append((0, 0, {
                "input_type_id": itype.id, "amount": amount,
            }))
        slip = self.env["hr.payslip"].create({
            "name": "Nómina prueba",
            "employee_id": employee.id,
            "contract_id": contract.id,
            "struct_id": self.structure.id,
            "date_from": date_from,
            "date_to": date_to,
            "input_line_ids": input_lines,
        })
        slip.compute_sheet()
        return slip

    def _line(self, slip, code):
        line = slip.line_ids.filtered(lambda l: l.code == code)
        return round(line.total, 2) if line else 0.0

    # ------------------------------------------------------------------
    def test_horas_extra_diurnas_y_nocturnas(self):
        """§4.3: HE diurna x1.5, nocturna x2.0 sobre valor hora = wage/240."""
        emp = self._employee("HE")
        con = self._contract(emp, 4800.0)
        slip = self._payslip(emp, con, inputs={"HE_DIURNA": 10, "HE_NOCTURNA": 5})
        self.assertEqual(self._line(slip, "HEXTD"), 300.00)   # 20 x1.5 x10
        self.assertEqual(self._line(slip, "HEXTN"), 200.00)   # 20 x2.0 x5
        # Base IGSS = ordinario + HE = 5300; afecta a IGSS
        self.assertEqual(self._line(slip, "IGSSLAB"), -255.99)
        self.assertEqual(self._line(slip, "GROSS"), 5550.00)

    def test_comisiones_afectan_igss(self):
        """§4.5/4.9: las comisiones entran en la base de IGSS."""
        emp = self._employee("Comis")
        con = self._contract(emp, 5000.0)
        slip = self._payslip(emp, con, inputs={"COMIS": 1000})
        self.assertEqual(self._line(slip, "COMIS"), 1000.00)
        self.assertEqual(self._line(slip, "IGSSLAB"), -289.80)  # (5000+1000)*4.83%

    def test_bonificacion_incentivo_excluida_de_igss(self):
        """§4.9.4: la Bonificación Incentivo NO forma parte de la base IGSS."""
        emp = self._employee("BonIexcl")
        con = self._contract(emp, 5000.0, bonif=250.0)
        slip = self._payslip(emp, con)
        self.assertEqual(self._line(slip, "BONINC"), 250.00)
        # IGSS solo sobre 5000, no sobre 5250
        self.assertEqual(self._line(slip, "IGSSLAB"), -241.50)
        # IGSS patronal 12.67% sobre 5000
        self.assertEqual(self._line(slip, "IGSSPAT"), 633.50)

    def test_empleado_no_afiliado_igss(self):
        """Sin afiliación IGSS no se aplica descuento ni cuota patronal."""
        emp = self._employee("SinIGSS", igss=False)
        con = self._contract(emp, 5000.0)
        slip = self._payslip(emp, con)
        self.assertEqual(self._line(slip, "IGSSLAB"), 0.0)
        self.assertEqual(self._line(slip, "IGSSPAT"), 0.0)

    def test_salario_proporcional_ingreso_mitad_periodo(self):
        """§4.1.2: ingreso a mitad de período -> proporcional por días calendario."""
        emp = self._employee("Parcial")
        con = self._contract(emp, 6000.0, date_start="2026-06-16")
        slip = self._payslip(emp, con)
        # 16 al 30 de junio = 15 días; 6000/30*15
        self.assertEqual(self._line(slip, "SALORD"), 3000.00)

    def test_salario_por_tramos_cambio_salarial(self):
        """§4.1.4: cambio de salario en el período -> prorrateo por tramos."""
        emp = self._employee("Tramos")
        self._contract(emp, 6000.0, date_start="2025-01-01",
                       date_end="2026-06-14", state="close")
        con2 = self._contract(emp, 8000.0, date_start="2026-06-15")
        slip = self._payslip(emp, con2)
        # 6000/30*14 + 8000/30*16 = 2800 + 4266.67
        self.assertEqual(self._line(slip, "SALORD"), 7066.67)

    def test_salario_quincenal(self):
        """Quincena: no paga el mes completo; prorratea por días (mensual/30)."""
        emp = self._employee("Quincena")
        con = self._contract(emp, 9000.0)
        slip = self._payslip(emp, con, date_from="2026-08-01", date_to="2026-08-14")
        # 9000/30 x 14 = 4200
        self.assertEqual(self._line(slip, "SALORD"), 4200.00)

    def test_mes_completo_paga_salario_completo(self):
        """Mes calendario completo: paga el salario mensual sin prorratear."""
        emp = self._employee("MesCompleto")
        con = self._contract(emp, 9000.0)
        slip = self._payslip(emp, con, date_from="2026-08-01", date_to="2026-08-31")
        self.assertEqual(self._line(slip, "SALORD"), 9000.00)

    def test_otras_deducciones(self):
        """§4.13: otras deducciones se restan del líquido."""
        emp = self._employee("OtrDed")
        con = self._contract(emp, 5000.0)
        slip = self._payslip(emp, con, inputs={"OTRDED": 300})
        self.assertEqual(self._line(slip, "OTRDED"), -300.00)
