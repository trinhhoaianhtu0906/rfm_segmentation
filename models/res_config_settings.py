from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    rfm_source = fields.Selection(related="company_id.rfm_source", readonly=False)
    rfm_period_months = fields.Integer(
        related="company_id.rfm_period_months", readonly=False
    )
    rfm_last_compute = fields.Datetime(related="company_id.rfm_last_compute")

    def action_rfm_compute(self):
        self.execute()
        return self.env["rfm.segment"].action_compute_rfm()
