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
            "name": "Lunes a viernes 8-17 con almuerzo",
            "tz": "America/Guatemala",
            "attendance_ids": [(5, 0, 0)] + [
                (0, 0, {"name": "d%s %s" % (d, p), "dayofweek": str(d),
                        "hour_from": f, "hour_to": t, "day_period": p})
                for d in range(5)
                # Con la franja de almuerzo, como el horario real de MRO: la
                # asistencia la descuenta de las horas registradas.
                for f, t, p in ((8, 12, "morning"), (12, 13, "lunch"),
                                (13, 17, "afternoon"))],
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
        self.assertIn("Diferencia", slip.l10n_gt_overtime_detail)

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

    def _all_week_calendar(self):
        """El horario de prueba también con sábado y domingo (como la jornada de obra)."""
        self.calendar.write({"attendance_ids": [
            (0, 0, {"name": "d%s %s" % (d, p), "dayofweek": str(d),
                    "hour_from": f, "hour_to": t, "day_period": p})
            for d in (5, 6)
            for f, t, p in ((8, 12, "morning"), (12, 13, "lunch"), (13, 17, "afternoon"))]})

    def test_asueto_todo_es_extra(self):
        """En un día festivo configurado, todo el tiempo trabajado es extra (arts.
        128-129); el día siguiente, normal, no genera nada."""
        self.env["resource.calendar.leaves"].create({
            "name": "Día de la Revolución",
            "date_from": datetime(2026, 10, 20, 6, 0), "date_to": datetime(2026, 10, 21, 5, 59, 59),
            "company_id": self.env.company.id,
        })
        a20 = self._att(20, 8.0, 17.0)
        self._att(21, 8.0, 17.0)
        slip = self._slip()
        self.assertGreater(a20.worked_hours, 7.5)
        self.assertAlmostEqual(slip.l10n_gt_overtime_detected, round(a20.worked_hours, 2), places=2)
        self.assertEqual(slip.l10n_gt_holiday_worked, 1)
        self.assertEqual(slip.l10n_gt_holiday_worked_dates, "20/10")
        self.assertIn("asueto", slip.l10n_gt_overtime_detail)

    def test_septimo_dia_es_descanso_trabajado(self):
        """Regla '7.º día seguido': de siete días seguidos de jornada normal, el 7.º
        es descanso trabajado y todas sus horas son extra."""
        self.env.company.l10n_gt_rest_day_rule = "seventh"
        self._all_week_calendar()
        atts = self.env["hr.attendance"]
        for day in range(19, 26):  # lun 19 a dom 25
            atts |= self._att(day, 8.0, 17.0)
        slip = self._slip()
        septimo = atts.filtered(lambda a: a.check_in.day == 25 or a.check_in.day == 26)
        self.assertEqual(slip.l10n_gt_rest_worked, 1)
        self.assertAlmostEqual(slip.l10n_gt_overtime_detected, round(septimo.worked_hours, 2), places=2)
        self.assertIn("descanso", slip.l10n_gt_overtime_detail)

    def test_racha_viene_del_mes_anterior(self):
        """La racha se cuenta desde antes del período: si trabajó del 26 al 30 de
        septiembre, el 2 de octubre ya es el 7.º día seguido."""
        self.env.company.l10n_gt_rest_day_rule = "seventh"
        self._all_week_calendar()
        def att_sep(day):
            local = self.tz.localize(datetime(2026, 9, day, 8, 0))
            utc = local.astimezone(pytz.utc).replace(tzinfo=None)
            return self.env["hr.attendance"].create({
                "employee_id": self.emp.id, "check_in": utc,
                "check_out": utc.replace(hour=utc.hour + 9)})
        for day in range(26, 31):
            att_sep(day)
        self._att(1, 8.0, 17.0)
        a2 = self._att(2, 8.0, 17.0)
        slip = self._slip()
        self.assertEqual(slip.l10n_gt_rest_worked, 1)
        self.assertAlmostEqual(slip.l10n_gt_overtime_detected, round(a2.worked_hours, 2), places=2)

    def test_domingo_es_descanso_trabajado(self):
        """Regla 'Domingo' (por defecto): las horas de un domingo trabajado son
        todas extra; de lunes a sábado, solo lo que pase de la jornada."""
        self.env.company.l10n_gt_rest_day_rule = "sunday"
        self._all_week_calendar()
        atts = self.env["hr.attendance"]
        for day in range(19, 26):  # lun 19 a dom 25
            atts |= self._att(day, 8.0, 17.0)
        slip = self._slip()
        domingo = atts.filtered(lambda a: a.check_in.day in (25, 26))
        self.assertEqual(slip.l10n_gt_rest_worked, 1)
        self.assertAlmostEqual(slip.l10n_gt_overtime_detected, round(domingo.worked_hours, 2), places=2)

    def test_compensa_horas_estudiante(self):
        """Quien compensa: las horas de más reponen primero el sábado no trabajado
        (viernes y domingo sí trabajó); solo lo que sobra es extra."""
        # (Regla del 7.º día: el domingo 25 cuenta como día normal de la rotación.)
        self.env.company.l10n_gt_rest_day_rule = "seventh"
        self._all_week_calendar()
        self.contract.l10n_gt_overtime_compensates = True
        # Lun 19 a dom 25: 6 días de 12 h de jornada (11 h efectivas = +3 h c/u),
        # sábado 24 sin asistencia (estudia) → 6 x 3 = 18 h de más − 8 h = 10 h.
        atts = self.env["hr.attendance"]
        for day in (19, 20, 21, 22, 23, 25):
            atts |= self._att(day, 7.0, 19.0)
        slip = self._slip()
        extra = sum(a.worked_hours for a in atts) - 8.0 * 6
        self.assertAlmostEqual(slip.l10n_gt_overtime_detected, round(extra - 8.0, 2), places=2)
        self.assertIn("se repone", slip.l10n_gt_overtime_detail)
        # Sin la marca, se recomiendan todas las horas de más.
        self.contract.l10n_gt_overtime_compensates = False
        slip.invalidate_recordset()
        self.assertAlmostEqual(slip.l10n_gt_overtime_detected, round(extra, 2), places=2)
