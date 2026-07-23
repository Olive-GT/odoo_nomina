# -*- coding: utf-8 -*-
"""Los anticipos dejan de tener modelo propio (l10n.gt.advance): ahora viven como
líneas del Estado de Cuenta. Se eliminan las tablas del modelo retirado para que la
actualización no tropiece con datos huérfanos."""


def migrate(cr, version):
    if not version:
        return
    cr.execute("DROP TABLE IF EXISTS l10n_gt_advance_recovery CASCADE")
    cr.execute("DROP TABLE IF EXISTS l10n_gt_advance CASCADE")
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'l10n_gt_payroll_loans'
           AND (model IN ('l10n.gt.advance', 'l10n.gt.advance.recovery')
                OR name LIKE 'seq_l10n_gt_advance%'
                OR name LIKE 'access_advance%'
                OR name IN ('view_advance_list', 'view_advance_form',
                            'view_advance_search', 'action_advance',
                            'menu_advance'))
    """)
