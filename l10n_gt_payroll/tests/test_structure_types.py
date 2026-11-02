# -*- coding: utf-8 -*-
"""Los dos tipos de nómina GT (Mensual y Quincenal) usan la estructura GT: un
recibo generado sin estructura explícita (como lo hace "Generar recibos" del
lote) la toma del tipo del contrato y no sale en 0."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_gt")
class TestStructureTypes(TransactionCase):

    def _slip(self, type_xmlid, batch=None):
        stype = self.env.ref(type_xmlid)
        emp = self.env["hr.employee"].create({
            "name": "Tipo %s" % stype.name, "l10n_gt_igss_applies": True})
        contract = self.env["hr.contract"].create({
            "name": "c", "employee_id": emp.id, "wage": 5000.0,
            "l10n_gt_bonif_incentivo": 250.0, "state": "open",
            "date_start": "2026-01-01", "structure_type_id": stype.id,
        })
        return self.env["hr.payslip"].create({
            "name": "n", "employee_id": emp.id, "contract_id": contract.id,
            "date_from": "2026-09-01", "date_to": "2026-09-30",
            "payslip_run_id": batch.id if batch else False,
        })

    def test_ambos_tipos_toman_estructura_gt(self):
        structure = self.env.ref("l10n_gt_payroll.structure_gt_ordinaria")
        for xmlid in ("l10n_gt_payroll.structure_type_gt_mensual",
                      "l10n_gt_payroll.structure_type_gt_quincenal"):
            self.assertEqual(self.env.ref(xmlid).default_struct_id, structure)
            slip = self._slip(xmlid)
            self.assertEqual(slip.struct_id, structure)
            slip.compute_sheet()
            net = sum(slip.line_ids.filtered(lambda l: l.code == "NET").mapped("total"))
            self.assertGreater(net, 0)

    def test_calcular_lote_asigna_estructura_faltante(self):
        batch = self.env["hr.payslip.run"].create({
            "name": "Lote", "date_start": "2026-09-01", "date_end": "2026-09-30"})
        slip = self._slip("l10n_gt_payroll.structure_type_gt_quincenal", batch)
        slip.struct_id = False
        batch.action_gt_compute()
        self.assertTrue(slip.struct_id)
        self.assertTrue(slip.line_ids.filtered(lambda l: l.code == "NET"))
