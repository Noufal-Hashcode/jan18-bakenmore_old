from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    is_omit_move_line = fields.Boolean(string="Omit Move Line",Default=False)


class AccountAccountStockPickingType(models.Model):
    _inherit = 'account.account'

    opening_balance = fields.Monetary(string="Opening Balance", compute='_compute_opening_debit_credit', help="Opening balance value for this account.", store='True')
    current_balance = fields.Float(compute='_compute_current_balance', store='True')
