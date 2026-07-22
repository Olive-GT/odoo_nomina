# -*- coding: utf-8 -*-
from calendar import monthrange

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    @api.model
    def _get_email_template(self):
        """Bloquea el correo automático de "nuevo recibo disponible" que Odoo envía
        al confirmar la nómina.

        Odoo lo dispara en hr.payslip._generate_pdf() con
        `if template: template.send_mail(...)`. Al devolver un recordset vacío, el
        `if template` da falso y NO se envía nada — pero el PDF adjunto SÍ se sigue
        generando (esa parte no depende de la plantilla).

        El envío queda bajo control manual: el botón "Enviar recibo por correo"
        (action_l10n_gt_send_payslip) reactiva la plantilla vía contexto.
        """
        if self.env.context.get("l10n_gt_send_payslip_email"):
            return super()._get_email_template()
        return self.env["mail.template"]

    def action_l10n_gt_send_payslip(self):
        """Envío controlado del recibo por correo (cuando el usuario lo decide)."""
        self.ensure_one()
        template = self.with_context(
            l10n_gt_send_payslip_email=True)._get_email_template()
        if not template:
            raise UserError(
                "No se encontró la plantilla de correo del recibo de nómina "
                "(hr_payroll.mail_template_new_payslip)."
            )
        template.send_mail(
            self.id, email_layout_xmlid="mail.mail_notification_light",
            force_send=True,
        )
        self.message_post(
            body="Recibo de nómina enviado por correo a %s."
                 % (self.employee_id.name or "")
        )
        return True

    l10n_gt_unpaid_days = fields.Float(
        string="Faltas / días no pagados",
        default=0.0,
        help="Días no laborados y NO pagados del mes (faltas injustificadas, "
             "suspensiones sin goce de salario, permisos sin goce). Cada día "
             "descuenta el salario diario (sueldo mensual ÷ 30) del salario "
             "ordinario, lo que a su vez reduce el IGSS y el líquido. Las "
             "vacaciones y suspensiones del IGSS con goce NO se cuentan aquí. "
             "Después de cambiarlo, vuelve a pulsar 'Calcular hoja'.",
    )

    @api.onchange("employee_id", "contract_id", "date_from", "date_to")
    def _l10n_gt_snap_full_month(self):
        """En Guatemala el período de cálculo es SIEMPRE el mes completo (IGSS e
        ISR son mensuales). Ajusta automáticamente el período al mes calendario,
        sin importar el tipo de estructura del contrato. El pago quincenal/semanal
        se maneja con los comprobantes, no cambiando el período de cálculo."""
        if not self.date_from:
            return
        d = self.date_from
        first = d.replace(day=1)
        last = d.replace(day=monthrange(d.year, d.month)[1])
        if self.date_from != first:
            self.date_from = first
        if self.date_to != last:
            self.date_to = last

    @api.onchange("employee_id", "contract_id")
    def _l10n_gt_default_struct(self):
        """Hereda la estructura de cálculo del contrato (auto-rellena la Estructura
        del recibo), para no tener que seleccionarla a mano."""
        structure = self.env.ref(
            "l10n_gt_payroll.structure_gt_ordinaria", raise_if_not_found=False)
        if (structure and self.contract_id and not self.struct_id
                and self.contract_id.structure_type_id == structure.type_id):
            self.struct_id = structure

    @api.constrains("employee_id", "date_from", "date_to", "struct_id", "state")
    def _check_l10n_gt_no_duplicate(self):
        """§7.1: no permitir dos nóminas para el mismo empleado y período
        (misma estructura y fechas traslapadas)."""
        for slip in self.filtered(lambda s: s.state != "cancel"):
            if not (slip.employee_id and slip.date_from and slip.date_to
                    and slip.struct_id):
                continue
            dup = self.search_count([
                ("id", "!=", slip.id),
                ("employee_id", "=", slip.employee_id.id),
                ("company_id", "=", slip.company_id.id),
                ("struct_id", "=", slip.struct_id.id),
                ("state", "!=", "cancel"),
                ("date_from", "<=", slip.date_to),
                ("date_to", ">=", slip.date_from),
            ])
            if dup:
                raise ValidationError(
                    "Ya existe un recibo para %s con la misma estructura y un "
                    "período que se traslapa. No se permite generar dos nóminas "
                    "del mismo empleado y período (§7.1)." % slip.employee_id.name
                )

    def _l10n_gt_param(self, code):
        """Valor de un parámetro legal vigente a la fecha del recibo (§7.3).

        Reemplaza a payslip.rule_parameter(), inexistente en Odoo 18.
        """
        self.ensure_one()
        return self.env["hr.rule.parameter"]._get_parameter_from_code(
            code, self.date_to
        )

    def _l10n_gt_input(self, code):
        """Monto de una novedad (input) del recibo por código.

        En Odoo 18 el `inputs` del contexto de reglas es un dict; acceder por
        atributo (inputs.CODE) falla. Este helper lee las líneas directamente.
        """
        self.ensure_one()
        lines = self.input_line_ids.filtered(
            lambda l: l.input_type_id.code == code)
        return sum(lines.mapped("amount"))

    # ------------------------------------------------------------------
    # Días laborados y período (base calendario, §4.1.2)
    # ------------------------------------------------------------------
    def _l10n_gt_contracts_in_period(self):
        """Contratos del empleado que solapan el período del recibo."""
        self.ensure_one()
        return self.env["hr.contract"].search([
            ("employee_id", "=", self.employee_id.id),
            ("state", "in", ("open", "close")),
            ("date_start", "<=", self.date_to),
            "|", ("date_end", "=", False), ("date_end", ">=", self.date_from),
        ], order="date_start")

    def _l10n_gt_worked_days(self):
        """Días calendario laborados en el período (§4.1.2).

        En Guatemala la proporción del salario se calcula sobre días calendario
        (salario diario = mensual / 30), no sobre días hábiles. Para un mes
        completo devuelve los días del período (p.ej. 30).
        """
        self.ensure_one()
        contracts = self._l10n_gt_contracts_in_period()
        if not contracts:
            return (self.date_to - self.date_from).days + 1
        total = 0
        for c in contracts:
            ini = max(self.date_from, c.date_start)
            fin = min(self.date_to, c.date_end or self.date_to)
            dias = (fin - ini).days + 1
            if dias > 0:
                total += dias
        return total

    def _l10n_gt_is_full_period(self):
        """True si la relación laboral cubre todo el período (§4.1.2).

        Se basa en la cobertura del contrato, no en días hábiles: un empleado
        activo todo el mes recibe el salario completo aunque el mes tenga fines
        de semana o asuetos.
        """
        self.ensure_one()
        contracts = self._l10n_gt_contracts_in_period()
        if not contracts:
            return bool(self.contract_id)
        starts_covered = min(contracts.mapped("date_start")) <= self.date_from
        ends = [c.date_end or self.date_to for c in contracts]
        ends_covered = max(ends) >= self.date_to
        return starts_covered and ends_covered

    def _l10n_gt_is_full_calendar_month(self):
        """True si el período es exactamente un mes calendario completo.

        Distingue una nómina mensual (paga salario completo) de una quincena o
        de un mes parcial (que se prorratean por días).
        """
        self.ensure_one()
        from calendar import monthrange
        df, dt = self.date_from, self.date_to
        if df.day != 1 or df.month != dt.month or df.year != dt.year:
            return False
        return dt.day == monthrange(df.year, df.month)[1]

    def _l10n_gt_paid_days(self):
        """Días efectivamente pagados del período (base GT de 30 días − faltas).

        En Guatemala el salario se liquida sobre un mes de 30 días (sueldo diario =
        mensual ÷ 30). Un mes completo = 30 días pagados; las faltas no pagadas se
        restan. Para períodos parciales (ingreso/egreso a mitad de mes) se usa la
        cobertura del contrato en días calendario (tope 30).
        """
        self.ensure_one()
        unpaid = self.l10n_gt_unpaid_days or 0.0
        if self._l10n_gt_is_full_calendar_month() and self._l10n_gt_is_full_period():
            base = 30.0
        else:
            base = min(self._l10n_gt_worked_days(), 30.0)
        return max(base - unpaid, 0.0)

    def _l10n_gt_prorate(self, monthly_amount):
        """Prorratea un monto mensual al período (salario diario = mensual/30).

        Devuelve el monto completo solo si el período es un mes completo y el
        empleado estuvo activo todo el mes; en otro caso, mensual/30 x días.
        """
        self.ensure_one()
        if self._l10n_gt_is_full_calendar_month() and self._l10n_gt_is_full_period():
            return monthly_amount
        return (monthly_amount / 30.0) * self._l10n_gt_worked_days()

    # ------------------------------------------------------------------
    # Salario ordinario con tramos de contrato (§4.1.4)
    # ------------------------------------------------------------------
    def _l10n_gt_ordinary_salary(self):
        """Salario ordinario del período considerando cambios salariales.

        - Un único contrato que cubre todo el período: salario completo.
        - Ingreso/egreso a mitad del período: proporcional por días calendario
          (salario diario = wage / 30).
        - Cambio de salario en el período: proporcional por tramos.
        """
        self.ensure_one()
        contracts = self._l10n_gt_contracts_in_period()
        if not contracts:
            base = self.contract_id.wage if self.contract_id else 0.0
        elif (len(contracts) == 1 and self._l10n_gt_is_full_calendar_month()
                and self._l10n_gt_is_full_period()):
            base = contracts.wage
        else:
            base = 0.0
            for c in contracts:
                ini = max(self.date_from, c.date_start)
                fin = min(self.date_to, c.date_end or self.date_to)
                dias = (fin - ini).days + 1
                if dias <= 0:
                    continue
                base += (c.wage / 30.0) * dias

        # Descuento por faltas no pagadas (salario diario = mensual ÷ 30).
        unpaid = self.l10n_gt_unpaid_days or 0.0
        if unpaid > 0:
            ref_wage = self.contract_id.wage if self.contract_id else (
                contracts[:1].wage if contracts else 0.0)
            base -= (ref_wage / 30.0) * unpaid
        return max(base, 0.0)
