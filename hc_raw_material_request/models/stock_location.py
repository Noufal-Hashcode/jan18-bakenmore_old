# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from collections import defaultdict


class StockLocation(models.Model):
    _inherit = ['stock.location']

    is_approval_required = fields.Boolean('Is Required Approval', help="authority to approve to transfer request")
