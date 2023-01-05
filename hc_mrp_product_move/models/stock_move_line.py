# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from collections import defaultdict
from odoo.exceptions import Warning, UserError, ValidationError
from datetime import datetime, date


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    mrp_product_id = fields.Many2one('product.product', 'MRP Product', store=True,
                                                       compute='_compute_mrp_product_id', copy=False)
    mrp_product_category_id = fields.Many2one('product.category', 'MRP Product Category', store=True,
                                     compute='_compute_mrp_product_category_id', copy=False)

    @api.depends('production_id')
    def _compute_mrp_product_id(self):
        for rec in self:
            if rec.production_id:
                if rec.production_id and rec.production_id.product_id:
                    rec.mrp_product_id = rec.production_id.product_id.id
                else:
                    rec.mrp_product_id = False
            else:
                rec.mrp_product_id = False

    @api.depends('production_id', 'mrp_product_id')
    def _compute_mrp_product_category_id(self):
        for rec in self:
            if rec.mrp_product_id:
                if rec.mrp_product_id and rec.mrp_product_id.categ_id:
                    rec.mrp_product_category_id = rec.mrp_product_id.categ_id.id
                else:
                    rec.mrp_product_category_id = False
            else:
                rec.mrp_product_category_id = False

