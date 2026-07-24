# -*- coding: utf-8 -*-
"""Se retiran los préstamos formales (l10n.gt.loan): los anticipos viven como líneas
del Estado de Cuenta. Se eliminan sus tablas y metadatos."""


def migrate(cr, version):
    if not version:
        return
    cr.execute("DROP TABLE IF EXISTS l10n_gt_loan_line CASCADE")
    cr.execute("DROP TABLE IF EXISTS l10n_gt_loan CASCADE")
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'l10n_gt_payroll_loans'
           AND (name IN ('rule_antic', 'rule_prest', 'seq_l10n_gt_loan',
                         'view_loan_form', 'view_loan_list', 'action_loan',
                         'menu_loan')
                OR name LIKE 'access_loan%')
    """)
