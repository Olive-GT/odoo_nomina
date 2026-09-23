# -*- coding: utf-8 -*-
"""Vacaciones desde el recibo (§4.6): gozadas y pagadas en el mismo lugar, contra
el mismo saldo; solo las pagadas generan la línea VAC que llega a la nómina."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestVacationsFromPayslip(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        cls.employee = cls.env["hr.employee"].create({
            "name": "Edgar Coc",
            "l10n_gt_dpi": "3013104400102",
            "l10n_gt_igss_applies": True,
            # 10 días pendientes al corte, sin acumulación previa que estorbe.
            "l10n_gt_opening_date": "2026-08-01",
            "l10n_gt_opening_vacation_days": 10.0,
        })
        cls.contract = cls.env["hr.contract"].create({
            "name": "Contrato Edgar",
            "employee_id": cls.employee.id,
            "wage": 8000.0,
            "l10n_gt_bonif_incentivo": 250.0,
            "state": "open",
            "date_start": "2024-01-01",
            "structure_type_id": cls.structure.type_id.id,
        })

    def _slip(self, **vals):
        base = {
            "name": "Recibo Edgar agosto 2026",
            "employee_id": self.employee.id,
            "contract_id": self.contract.id,
            "struct_id": self.structure.id,
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
        }
        base.update(vals)
        slip = self.env["hr.payslip"].create(base)
        slip.compute_sheet()
        return slip

    def _line(self, slip, code):
        return sum(slip.line_ids.filtered(lambda l: l.code == code).mapped("total"))

    def test_paid_days_generate_vac_line(self):
        """3 días pagados = 3 × (8000 × 12 / 365) = Q789.04 (anexo 8.6: Q276.16/día),
        afectos a IGSS y sumados al devengado y al líquido."""
        plain = self._slip()
        slip = self._slip(name="Con vacaciones", l10n_gt_vacation_paid_days=3.0,
                          date_from="2026-09-01", date_to="2026-09-30")
        vac = self._line(slip, "VAC")
        self.assertAlmostEqual(vac, 3 * 8000.0 * 12 / 365, places=2)
        self.assertAlmostEqual(vac, 789.04, places=2)
        # Entra al devengado, a la base IGSS y al líquido.
        self.assertAlmostEqual(
            self._line(slip, "GROSS") - self._line(plain, "GROSS"), vac, places=2)
        igss_rate = self.env["hr.rule.parameter"]._get_parameter_from_code(
            "l10n_gt_igss_laboral", slip.date_to)
        self.assertAlmostEqual(
            self._line(plain, "IGSSLAB") - self._line(slip, "IGSSLAB"),
            vac * igss_rate, places=2)
        self.assertAlmostEqual(
            self._line(slip, "NET") - self._line(plain, "NET"),
            vac * (1 - igss_rate), places=2)

    def test_taken_days_do_not_change_salary(self):
        plain = self._slip()
        slip = self._slip(name="Gozadas", l10n_gt_vacation_days=5.0,
                          date_from="2026-09-01", date_to="2026-09-30")
        self.assertEqual(self._line(slip, "VAC"), 0.0)
        self.assertAlmostEqual(
            self._line(slip, "NET"), self._line(plain, "NET"), places=2)

    def test_both_kinds_consume_same_balance(self):
        """Gozados + pagados bajan el mismo saldo al confirmar; al cancelar vuelven."""
        slip = self._slip(l10n_gt_vacation_days=2.0, l10n_gt_vacation_paid_days=3.0)
        # Apertura 10 días al 01/08 + 15/año acumulados hasta el 31/08.
        accrued = self.employee._l10n_gt_vacation_accrued_at(slip.date_to)
        self.assertAlmostEqual(accrued, 10.0 + 30 / 365.0 * 15.0, places=2)
        self.assertAlmostEqual(slip.l10n_gt_vacation_balance, accrued, places=2)
        slip.action_payslip_done()
        taken = self.env["l10n.gt.vacation.taken"].search(
            [("payslip_id", "=", slip.id)])
        self.assertEqual(len(taken), 2)
        self.assertEqual(
            {(t.kind, t.days) for t in taken}, {("gozadas", 2.0), ("pagadas", 3.0)})
        self.employee.invalidate_recordset()
        self.assertAlmostEqual(self.employee.l10n_gt_vacation_taken, 5.0, places=2)
        self.assertAlmostEqual(
            self.employee._l10n_gt_vacation_pending_at(slip.date_to),
            accrued - 5.0, places=2)
        # El saldo del propio recibo se muestra "antes de este recibo".
        slip.invalidate_recordset(["l10n_gt_vacation_balance"])
        self.assertAlmostEqual(slip.l10n_gt_vacation_balance, accrued, places=2)
        slip.action_payslip_cancel()
        self.assertFalse(self.env["l10n.gt.vacation.taken"].search(
            [("payslip_id", "=", slip.id)]))

    def test_paid_vacation_lowers_liability_once(self):
        """El pasivo de vacaciones baja por los días consumidos, no por un pago
        aparte (la línea VAC no es un pago del Estado de Cuenta)."""
        liab_before = self.employee.l10n_gt_liab_vacaciones
        slip = self._slip(l10n_gt_vacation_paid_days=3.0)
        slip.action_payslip_done()
        self.employee.invalidate_recordset()
        daily = self.employee._l10n_gt_daily_average(
            slip.date_to.replace(year=slip.date_to.year - 1), slip.date_to)
        self.assertAlmostEqual(
            liab_before - self.employee.l10n_gt_liab_vacaciones, 3 * daily, delta=1.0)

    def test_over_balance_warns(self):
        """Saldo 10: anotar 12 días avisa (sin bloquear); 8 no."""
        slip = self._slip()
        slip.l10n_gt_vacation_paid_days = 12.0
        self.assertIn("warning", slip._onchange_l10n_gt_vacation_days() or {})
        slip.l10n_gt_vacation_paid_days = 8.0
        self.assertFalse(slip._onchange_l10n_gt_vacation_days())

    def test_structure_offers_inputs(self):
        """Odoo 18 filtra 'Otras entradas' por struct_id.input_line_type_ids."""
        codes = set(self.structure.input_line_type_ids.mapped("code"))
        self.assertTrue({"HE_DIURNA", "HE_NOCTURNA", "COMIS", "BONIF",
                         "OTRDED"} <= codes)
