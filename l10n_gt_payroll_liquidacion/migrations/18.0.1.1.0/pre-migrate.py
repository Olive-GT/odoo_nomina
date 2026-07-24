# -*- coding: utf-8 -*-
"""La liquidación deja de ser un modelo aparte (l10n.gt.settlement): ahora es un
RECIBO de liquidación (finiquito) unificado con el estado de cuenta. Se retiran la
tabla y los metadatos del modelo para que la actualización no tropiece.

action_report_settlement y menu_settlement se conservan: el nuevo módulo los
actualiza para apuntar al recibo (hr.payslip)."""


def migrate(cr, version):
    if not version:
        return
    cr.execute("DROP TABLE IF EXISTS l10n_gt_settlement CASCADE")
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'l10n_gt_payroll_liquidacion'
           AND name IN ('view_settlement_form', 'view_settlement_list',
                        'action_settlement',
                        'access_settlement_user', 'access_settlement_manager',
                        'seq_l10n_gt_settlement')
    """)
