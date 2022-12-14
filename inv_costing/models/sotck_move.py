from odoo import api, fields, models, _
import datetime


class StockMove(models.Model):
    _inherit = "stock.move"

    def _prepare_account_move_vals(self, credit_account_id, debit_account_id, journal_id, qty, description, svl_id,
                                  cost):
        if self.picking_type_id.is_omit_move_line:


            return
        else:
            return super(StockMove, self)._prepare_account_move_vals(credit_account_id, debit_account_id, journal_id, qty,
                                                              description, svl_id, cost)

class StockValuationLayer(models.Model):
    _inherit = "stock.valuation.layer"

    def _validate_accounting_entries(self):
        if self.stock_move_id.picking_type_id.is_omit_move_line:

            print("inside _validate_accounting_entries")

            return
        else:
            return super(StockValuationLayer, self)._validate_accounting_entries()


        # if self.picking_type_id.code == 'internal':
        #     self.ensure_one()
        #     AccountMove = self.env['account.move'].with_context(default_journal_id=journal_id)
        #
        #     move_lines = self._prepare_account_move_line(qty, cost, credit_account_id, debit_account_id, description)
        #     if move_lines:
        #         date = self._context.get('force_period_date', fields.Date.context_today(self))
        #         new_account_move = AccountMove.sudo().create({
        #             'journal_id': journal_id,
        #             'line_ids': move_lines,
        #             'date': self.picking_id.scheduled_date.date(),
        #             'ref': description,
        #             'stock_move_id': self.id,
        #             'stock_valuation_layer_ids': [(6, None, [svl_id])],
        #             'type': 'entry',
        #         })
        #         new_account_move.post()
        #         return
        # return super(StockMove, self)._create_account_move_line(credit_account_id, debit_account_id, journal_id, qty,
        #                                                         description, svl_id, cost)


class ProductCategory(models.Model):
    _inherit = 'product.category'

    @api.constrains('property_stock_valuation_account_id', 'property_stock_account_output_categ_id', 'property_stock_account_input_categ_id')
    def _check_valuation_accouts(self):
        # Prevent to set the valuation account as the input or output account.
        for category in self:
            return False
