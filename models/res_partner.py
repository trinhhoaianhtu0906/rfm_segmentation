from odoo import api, fields, models

RFM_GROUP = "rfm_segmentation.group_rfm_user"


class ResPartner(models.Model):
    _inherit = "res.partner"

    rfm_recency_days = fields.Integer(
        string="Days since last purchase", readonly=True, groups=RFM_GROUP
    )
    rfm_frequency = fields.Integer(string="Purchases", readonly=True, groups=RFM_GROUP)
    rfm_monetary = fields.Float(string="Revenue", readonly=True, groups=RFM_GROUP)
    rfm_recency_score = fields.Integer(
        string="Recency score", readonly=True, groups=RFM_GROUP
    )
    rfm_frequency_score = fields.Integer(
        string="Frequency score", readonly=True, groups=RFM_GROUP
    )
    rfm_monetary_score = fields.Integer(
        string="Monetary score", readonly=True, groups=RFM_GROUP
    )
    rfm_score = fields.Char(
        string="RFM score",
        compute="_compute_rfm_score",
        store=True,
        groups=RFM_GROUP,
    )
    rfm_segment_id = fields.Many2one(
        "rfm.segment",
        string="RFM segment",
        index=True,
        readonly=True,
        groups=RFM_GROUP,
    )

    @api.depends("rfm_recency_score", "rfm_frequency_score", "rfm_monetary_score")
    def _compute_rfm_score(self):
        for partner in self:
            scores = (
                partner.rfm_recency_score,
                partner.rfm_frequency_score,
                partner.rfm_monetary_score,
            )
            partner.rfm_score = "".join(map(str, scores)) if all(scores) else False
