# -*- coding: utf-8 -*-
"""Pruebas profundas de liquidaciones (§4.16, §5)."""
from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "l10n_gt")
class TestSettlementDeep(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.struct_type = cls.env.ref("l10n_gt_payroll.structure_type_gt_mensual")

    def _emp_con(self, wage=8000.0, date_start="2024-01-01"):
        emp = self.env["hr.employee"].create({"name": "Liq"})
        con = self.env["hr.contract"].create({
            "name": "c", "employee_id": emp.id, "wage": wage, "state": "open",
            "date_start": date_start,
            "structure_type_id": self.struct_type.id,
        })
        return emp, con

    def _settlement(self, emp, reason, date_end="2026-07-17"):
        s = self.env["l10n.gt.settlement"].create({
            "employee_id": emp.id, "date_end": date_end, "reason": reason,
        })
        s.action_compute()
        return s

    def test_renuncia_sin_indemnizacion(self):
        """§4.16.4: la renuncia no genera indemnización."""
        emp, _ = self._emp_con()
        s = self._settlement(emp, "renuncia")
        self.assertFalse(s.has_indemnity)
        self.assertEqual(s.indemnizacion, 0.0)
        # pero sí aguinaldo y bono 14 proporcionales
        self.assertGreater(s.aguinaldo_prop, 0.0)
        self.assertGreater(s.bono14_prop, 0.0)

    def test_despido_con_indemnizacion(self):
        """El despido injustificado sí genera indemnización."""
        emp, _ = self._emp_con()
        s = self._settlement(emp, "despido_injustificado")
        self.assertTrue(s.has_indemnity)
        self.assertGreater(s.indemnizacion, 0.0)

    def test_empleado_pasa_a_inactivo_al_aprobar(self):
        """§5.6: al aprobar la liquidación el empleado queda inactivo."""
        emp, _ = self._emp_con()
        s = self._settlement(emp, "despido_injustificado")
        s.action_approve()
        self.assertEqual(s.state, "approved")
        self.assertFalse(emp.active)

    def test_no_dos_liquidaciones_misma_fecha(self):
        """§5.6: no se permite doble liquidación para el mismo empleado y fecha."""
        emp, _ = self._emp_con()
        self.env["l10n.gt.settlement"].create({
            "employee_id": emp.id, "date_end": "2026-07-17",
            "reason": "renuncia",
        })
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["l10n.gt.settlement"].create({
                "employee_id": emp.id, "date_end": "2026-07-17",
                "reason": "despido_injustificado",
            })
            self.env.flush_all()
