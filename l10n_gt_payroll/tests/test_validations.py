# -*- coding: utf-8 -*-
"""Validaciones y reglas de negocio (§3.2.3, §4.1.4, §4.2.4, §7)."""
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "l10n_gt")
class TestValidations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.struct_type = cls.env.ref(
            "l10n_gt_payroll.structure_type_gt_mensual")

    def test_dpi_debe_tener_13_digitos(self):
        with self.assertRaises(ValidationError):
            self.env["hr.employee"].create({
                "name": "DPI malo", "l10n_gt_dpi": "123",
            })

    def test_bonif_incentivo_no_supera_salario(self):
        """§4.2.4: la bonificación no puede superar el salario ordinario."""
        emp = self.env["hr.employee"].create({"name": "BonAlta"})
        with self.assertRaises(ValidationError):
            self.env["hr.contract"].create({
                "name": "c", "employee_id": emp.id, "wage": 1000.0,
                "l10n_gt_bonif_incentivo": 2000.0, "state": "open",
                "date_start": "2026-01-01",
                "structure_type_id": self.struct_type.id,
            })

    def test_salario_minimo_por_circunscripcion(self):
        """§4.1.4: el salario no puede ser inferior al mínimo de la zona."""
        zone = self.env["l10n.gt.economic.zone"].create({"name": "Z", "code": "Z1"})
        self.env["l10n.gt.minimum.wage"].create({
            "zone_id": zone.id, "date_from": "2026-01-01", "amount": 3500.0,
        })
        emp = self.env["hr.employee"].create({"name": "MinWage"})
        with self.assertRaises(ValidationError):
            self.env["hr.contract"].create({
                "name": "c", "employee_id": emp.id, "wage": 2000.0,
                "l10n_gt_economic_zone_id": zone.id, "state": "open",
                "date_start": "2026-06-01",
                "structure_type_id": self.struct_type.id,
            })

    def test_periodos_no_traslapados(self):
        """§3.2.3: no permitir períodos traslapados para el mismo tipo."""
        self.env["hr.payslip.run"].create({
            "name": "Jun", "date_start": "2026-06-01", "date_end": "2026-06-30",
            "l10n_gt_structure_type_id": self.struct_type.id,
        })
        with self.assertRaises(ValidationError):
            self.env["hr.payslip.run"].create({
                "name": "Jun2", "date_start": "2026-06-15",
                "date_end": "2026-07-15",
                "l10n_gt_structure_type_id": self.struct_type.id,
            })
