# -*- coding: utf-8 -*-
"""La nómina de sueldos y salarios en Excel se genera desde el lote con el
formato del cliente (encabezado, columnas, totales y firmas)."""
import io
import zipfile

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestNominaXlsx(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write({
            "l10n_gt_payroll_prepared_by": "Persona Elabora",
            "l10n_gt_payroll_approved_by": "Persona Aprueba",
        })
        structure = cls.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        employee = cls.env["hr.employee"].create({
            "name": "Empleado Excel", "l10n_gt_igss_applies": True})
        contract = cls.env["hr.contract"].create({
            "name": "Contrato Excel", "employee_id": employee.id, "wage": 5500.0,
            "l10n_gt_bonif_incentivo": 250.0, "state": "open",
            "date_start": "2026-04-29", "structure_type_id": structure.type_id.id,
        })
        cls.batch = cls.env["hr.payslip.run"].create({
            "name": "AGOSTO 2026", "date_start": "2026-08-01",
            "date_end": "2026-08-31"})
        slip = cls.env["hr.payslip"].create({
            "name": "Recibo Excel", "employee_id": employee.id,
            "contract_id": contract.id, "struct_id": structure.id,
            "payslip_run_id": cls.batch.id,
            "date_from": "2026-08-01", "date_to": "2026-08-31",
        })
        slip.compute_sheet()

    def _shared_strings(self, content):
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            return z.read("xl/sharedStrings.xml").decode()

    def test_xlsx_renders_client_format(self):
        content, ext = self.env["ir.actions.report"]._render_xlsx(
            "l10n_gt_payroll_report_xlsx.nomina_xlsx", self.batch.ids, None)
        self.assertEqual(ext, "xlsx")
        strings = self._shared_strings(content)
        for text in ("NÓMINA DE SUELDOS Y SALARIOS", "DEL 01 AL 31 DE AGOSTO 2026",
                     "Empleado Excel", "PRIMERA QUINCENA", "TOTAL LÍQUIDO",
                     "Elaborado por:", "Persona Elabora", "Persona Aprueba"):
            self.assertIn(text, strings)
