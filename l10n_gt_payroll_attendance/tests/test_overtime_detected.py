# -*- coding: utf-8 -*-
"""Horas extra detectadas por asistencia: se calculan contra el horario del
contrato, ignoran excesos de pocos minutos y NUNCA se suman al recibo."""
from datetime import datetime

import pytz

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestOvertimeDetected(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.calendar = cls.env["resource.calendar"].create({
            "name": "Lunes a viernes 8-12 / 13-17",
            "tz": "America/Guatemala",
            "attendance_ids": [(5, 0, 0)] + [
                (0, 0, {"name": "d%s %s" % (d, p), "dayofweek": str(d),
                        "hour_from": f, "hour_to": t, "day_period": p})
                for d in range(5)
                for f, t, p in ((8, 12, "morning"), (13, 17, "afternoon"))],
        })
        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        cls.emp = cls.env["hr.employee"].create({
            "name": "Empleado Asistencia", "l10n_gt_igss_applies": True,
            "resource_calendar_id": cls.calendar.id, "tz": "America/Guatemala"})
        cls.contract = cls.env["hr.contract"].create({
            "name": "c", "employee_id": cls.emp.id, "wage": 4800.0,
            "l10n_gt_bonif_incentivo": 250.0, "state": "open",
            "date_start": "2026-01-01", "resource_calendar_id": cls.calendar.id,
            "structure_type_id": cls.structure.type_id.id,
        })
        cls.tz = pytz.timezone("America/Guatemala")

    def _att(self, day, h_in, h_out):
        """Asistencia en hora local de Guatemala."""
        def utc(h):
            hh, mm = int(h), int(round((h - int(h)) * 60))
            local = self.tz.localize(datetime(2026, 10, day, hh, mm))
            return local.astimezone(pytz.utc).replace(tzinfo=None)
        return self.env["hr.attendance"].create({
            "employee_id": self.emp.id, "check_in": utc(h_in), "check_out": utc(h_out)})

    def _slip(self):
        slip = self.env["hr.payslip"].create({
            "name": "n", "employee_id": self.emp.id, "contract_id": self.contract.id,
            "struct_id": self.structure.id,
            "date_from": "2026-10-01", "date_to": "2026-10-31"})
        slip.compute_sheet()
        return slip

    def test_detecta_contra_horario_del_contrato(self):
        # Martes 27/10: 7:00-19:00 (12 h de jornada registrada vs 8 h del horario).
        a1 = self._att(27, 7.0, 19.0)
        # Miércoles 28/10: 8:00-17:05 → 5 minutos de más: no se recomienda.
        a2 = self._att(28, 8.0, 17.0 + 5 / 60)
        # Sábado 31/10: 8:00-12:00, el horario no prevé sábado → 4 h extra.
        a3 = self._att(31, 8.0, 12.0)
        slip = self._slip()
        esperado = (a1.worked_hours - 8.0) + a3.worked_hours
        self.assertGreater(a1.worked_hours, 8.0)
        self.assertLess(a2.worked_hours - 8.0, 0.25)
        self.assertAlmostEqual(slip.l10n_gt_overtime_detected, round(esperado, 2), places=2)
        self.assertEqual(slip.l10n_gt_overtime_detected_days, 2)
        self.assertEqual(slip.l10n_gt_overtime_calendar_id, self.calendar)
        self.assertIn("Extra", slip.l10n_gt_overtime_detail)

    def test_es_solo_recomendacion(self):
        """Con horas detectadas, el recibo NO incluye horas extra hasta que se
        capturan; las capturadas se reflejan aparte."""
        self._att(27, 7.0, 19.0)
        slip = self._slip()
        self.assertGreater(slip.l10n_gt_overtime_detected, 0)
        self.assertFalse(slip.line_ids.filtered(lambda l: l.code in ("HEXTD", "HEXTN")))
        self.assertEqual(slip.l10n_gt_overtime_captured, 0.0)
        itype = self.env["hr.payslip.input.type"].search([("code", "=", "HE_DIURNA")], limit=1)
        slip.write({"input_line_ids": [(0, 0, {"input_type_id": itype.id, "amount": 3.0})]})
        self.assertEqual(slip.l10n_gt_overtime_captured, 3.0)

    def test_sin_asistencias(self):
        slip = self._slip()
        self.assertEqual(slip.l10n_gt_overtime_detected, 0.0)
        self.assertFalse(slip.l10n_gt_overtime_detail)
        action = slip.action_l10n_gt_view_attendances()
        self.assertEqual(action["res_model"], "hr.attendance")
