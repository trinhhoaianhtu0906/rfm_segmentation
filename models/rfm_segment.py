from odoo import fields, models
from odoo.exceptions import AccessError

RFM_MANAGER_GROUP = "rfm_segmentation.group_rfm_manager"


class RfmSegment(models.Model):
    _name = "rfm.segment"
    _description = "RFM Segment"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
    r_min = fields.Integer(string="Recency from", default=1)
    r_max = fields.Integer(string="Recency to", default=5)
    f_min = fields.Integer(string="Frequency from", default=1)
    f_max = fields.Integer(string="Frequency to", default=5)
    partner_ids = fields.One2many("res.partner", "rfm_segment_id", string="Customers")
    partner_count = fields.Integer(
        string="Customer count", compute="_compute_partner_count"
    )

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "The segment code must be unique.",
    )
    _score_ranges = models.Constraint(
        "CHECK(1 <= r_min AND r_min <= r_max AND r_max <= 5"
        " AND 1 <= f_min AND f_min <= f_max AND f_max <= 5)",
        "Score ranges must go from 1 to 5, with the start not after the end.",
    )

    def _compute_partner_count(self):
        counts = dict(
            self.env["res.partner"]._read_group(
                [("rfm_segment_id", "in", self.ids)], ["rfm_segment_id"], ["__count"]
            )
        )
        for segment in self:
            segment.partner_count = counts.get(segment, 0)

    def _match(self, r_score, f_score):
        """Return the first segment of ``self`` whose ranges hold the scores."""
        return next(
            (
                segment
                for segment in self
                if segment.r_min <= r_score <= segment.r_max
                and segment.f_min <= f_score <= segment.f_max
            ),
            self.browse(),
        )

    def action_view_partners(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "res.partner",
            "view_mode": "list,form",
            "domain": [("rfm_segment_id", "=", self.id)],
        }

    def action_compute_rfm(self):
        if not self.env.user.has_group(RFM_MANAGER_GROUP):
            raise AccessError(
                self.env._("Only RFM managers can compute the RFM scores.")
            )
        self.env["rfm.calculator"]._compute_rfm(self.env.company)
        return {"type": "ir.actions.client", "tag": "reload"}
