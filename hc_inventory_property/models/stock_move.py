# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_round, float_is_zero
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.exceptions import UserError, ValidationError


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.depends('product_id', 'has_tracking', 'move_line_ids')
    def _compute_show_details_visible(self):
        super(StockMove, self)._compute_show_details_visible()
        for rec in self:
            if rec.picking_id and rec.picking_id.picking_type_id.code == 'incoming':
                if rec.product_id:
                    if rec.product_id.inventory_property != 'actual_expiry':
                        rec.show_details_visible = False

    @api.depends('state', 'picking_id', 'product_id')
    def _compute_is_quantity_done_editable(self):
        super(StockMove, self)._compute_is_quantity_done_editable()
        for rec in self:
            if rec.picking_id and rec.picking_id.picking_type_id.code == 'incoming':
                if rec.product_id:
                    if rec.product_id.inventory_property != 'actual_expiry':
                        rec.is_quantity_done_editable = True


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.onchange('product_id', 'product_uom_id')
    def _onchange_product_id(self):
        res = super(StockMoveLine, self)._onchange_product_id()
        if self.move_id.picking_id and self.move_id.picking_id.picking_type_id.code == 'incoming':
            if self.picking_type_use_create_lots:
                if self.product_id.use_expiration_date:
                    if self.product_id.inventory_property == 'actual_expiry':
                        self.expiration_date = False
                else:
                    self.expiration_date = False
        return res

    # @api.depends('product_id', 'picking_type_use_create_lots', 'lot_id.expiration_date')
    # def _compute_expiration_date(self):
    #     super(StockMoveLine, self)._compute_expiration_date()
    #     for move_line in self:
    #         if move_line.move_id.picking_id and move_line.move_id.picking_id.picking_type_id.code == 'incoming':
    #             if move_line.product_id.inventory_property == 'actual_expiry':
    #                 move_line.expiration_date = False
