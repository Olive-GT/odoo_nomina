# -*- coding: utf-8 -*-
"""Se retira la planilla independiente de Aguinaldo/Bono 14 (l10n.gt.benefit.run):
las prestaciones se manejan como provisiones + líneas de pago en el recibo. Se
eliminan sus tablas y metadatos para que la actualización no tropiece."""


def migrate(cr, version):
    if not version:
        return
    cr.execute("DROP TABLE IF EXISTS l10n_gt_benefit_line CASCADE")
    cr.execute("DROP TABLE IF EXISTS l10n_gt_benefit_run CASCADE")
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'l10n_gt_payroll_prestaciones'
           AND (model IN ('l10n.gt.benefit.run', 'l10n.gt.benefit.line')
                OR name IN ('view_benefit_run_form', 'view_benefit_run_list',
                            'action_benefit_run', 'menu_benefit_run',
                            'access_benefit_run_user', 'access_benefit_run_manager',
                            'access_benefit_line_user'))
    """)
