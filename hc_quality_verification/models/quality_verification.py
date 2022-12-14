# -*- coding: utf-8 -*-
from odoo import api, models, fields, _


class QualityVerification(models.Model):
    _inherit = ['quality.check']

    quality_state = fields.Selection(selection_add=[('verified', 'Verified')])

    def action_verified(self):
        self.quality_state = 'verified'
        return True
