# -*- coding: utf-8 -*-
"""Generación de recibos en lote para la nómina GT: no la bloquean las entradas
de trabajo encimadas (horas extra de asistencia) y el lote es de un solo mes."""
from datetime import datetime

from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestBatchGeneration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        cls.emp = cls.env["hr.employee"].create({
            "name": "Empleado Lote", "l10n_gt_igss_applies": True})
        cls.contract = cls.env["hr.contract"].create({
            "name": "c", "employee_id": cls.emp.id, "wage": 5000.0,
            "l10n_gt_bonif_incentivo": 250.0, "state": "open",
            "date_start": "2026-01-01",
            "structure_type_id": cls.env.ref(
                "l10n_gt_payroll.structure_type_gt_quincenal").id,
        })

    def _run(self, start="2026-10-01", end="2026-10-31"):
        return self.env["hr.payslip.run"].create({
            "name": "OCTUBRE", "date_start": start, "date_end": end})

    def _generate(self, run):
        wizard = self.env["hr.payslip.employees"].with_context(
            active_id=run.id, active_model="hr.payslip.run").create({
                "employee_ids": [(6, 0, self.emp.ids)]})
        return wizard.with_context(active_id=run.id).compute_sheet()

    def test_conflicto_de_entradas_no_bloquea(self):
        run = self._run()
        self.contract.generate_work_entries(
            datetime(2026, 10, 1).date(), datetime(2026, 10, 31).date())
        # Entrada de horas extra encimada sobre la jornada normal (como las crea
        # la asistencia con horas extra aprobadas).
        self.env["hr.work.entry"].create({
            "name": "Horas extra", "employee_id": self.emp.id,
            "contract_id": self.contract.id,
            "work_entry_type_id": self.env.ref("hr_work_entry.overtime_work_entry_type").id,
            "date_start": datetime(2026, 10, 27, 6, 0),
            "date_stop": datetime(2026, 10, 27, 23, 0),
        })
        self._generate(run)
        self.assertEqual(len(run.slip_ids), 1)
        slip = run.slip_ids
        self.assertEqual(slip.struct_id, self.structure)
        self.assertTrue(slip.line_ids.filtered(lambda l: l.code == "NET" and l.total > 0))

    def test_lote_de_dos_meses_no_se_permite(self):
        with self.assertRaises(ValidationError):
            self._run(end="2026-11-30")

    def test_generar_avisa_si_el_lote_abarca_dos_meses(self):
        run = self._run()
        # Lote antiguo guardado antes de la validación.
        self.env.cr.execute(
            "UPDATE hr_payslip_run SET date_end='2026-11-30' WHERE id=%s", (run.id,))
        run.invalidate_recordset()
        with self.assertRaises(UserError):
            self._generate(run)

    def test_fecha_fin_sigue_al_inicio(self):
        form = Form(self.env["hr.payslip.run"])
        form.name = "OCTUBRE"
        form.date_start = "2026-10-01"
        self.assertEqual(str(form.date_end), "2026-10-31")
