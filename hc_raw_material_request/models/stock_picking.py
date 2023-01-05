# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from collections import defaultdict
from odoo.exceptions import Warning, UserError, ValidationError
from datetime import datetime, date


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_approved = fields.Boolean(string='Approved', copy=False)
    approval_visibility = fields.Boolean(string='Approval Visibility', store=True,
                                          compute='_compute_approval_visibility', copy=False)

    @api.depends('state', 'is_approved', 'location_id')
    def _compute_approval_visibility(self):
        for record in self:
            if record.state != 'assigned':
                record.approval_visibility = False
            else:
                if record.location_id:
                    if record.location_id.is_approval_required:
                        record.approval_visibility = True
                        if record.is_approved:
                            record.approval_visibility = False
                    else:
                        record.approval_visibility = False
                else:
                    record.approval_visibility = False

    def approve(self):
        self.is_approved = True

    def button_validate(self):
        print("button_validate")
        if self.location_id:
            if self.location_id.is_approval_required:
                if not self.is_approved:
                    raise ValidationError(
                        _('You are not allowed to validate without approval'))
        return super().button_validate()


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    picking_ids = fields.Many2many('stock.picking', compute='_compute_picking_ids',
                                   string='Picking associated to this manufacturing order', store=True)
    delivery_count = fields.Integer(string='Delivery Orders', compute='_compute_picking_ids', store=True)

    def action_confirm(self):
        self._check_company()

        for production in self:
            delivery_count = 0
            picking_ids = []
            picking_type = self.env['stock.picking.type'].search([('sequence_code', '=', 'PC'),
                                                                  ('warehouse_id', '=',
                                                                   production.picking_type_id.warehouse_id.id)])
            if production.bom_id:
                production.consumption = production.bom_id.consumption
            # In case of Serial number tracking, force the UoM to the UoM of product
            if production.product_tracking == 'serial' and production.product_uom_id != production.product_id.uom_id:
                production.write({
                    'product_qty': production.product_uom_id._compute_quantity(production.product_qty,
                                                                               production.product_id.uom_id),
                    'product_uom_id': production.product_id.uom_id
                })
                for move_finish in production.move_finished_ids.filtered(
                        lambda m: m.product_id == production.product_id):
                    move_finish.write({
                        'product_uom_qty': move_finish.product_uom._compute_quantity(move_finish.product_uom_qty,
                                                                                     move_finish.product_id.uom_id),
                        'product_uom': move_finish.product_id.uom_id
                    })
            production.move_raw_ids._adjust_procure_method()

            if production.move_raw_ids:
                dry_items = []
                other_item = []
                source_location = self.env['stock.location'].search([('name', '=', 'Dry Store')])
                for i in production.move_raw_ids:
                    if i.product_id.categ_id.name != 'Dry':
                        #     picking_type = self.env['stock.picking.type'].search([('sequence_code', '=', 'INT TRF')])
                        #     move_data_dict = {
                        #         'name': 'Mo Picking Move',
                        #         'location_id': picking_type.default_location_src_id.id,
                        #         'location_dest_id': picking_type.default_location_dest_id.id,
                        #         'product_id': i.product_id.id,
                        #         'product_uom': i.product_uom.id,
                        #         'product_uom_qty': i.product_uom_qty,
                        #     }
                        #     dry_items.append((0, 0,move_data_dict))
                        # else:  	PC
                        picking_type = self.env['stock.picking.type'].search([('sequence_code', '=', 'PC')])
                        move_data_dict = {
                            'name': 'Mo Picking Move',
                            'location_id': picking_type.default_location_src_id.id,
                            'location_dest_id': picking_type.default_location_dest_id.id,
                            'product_id': i.product_id.id,
                            'product_uom': i.product_uom.id,
                            'product_uom_qty': i.product_uom_qty,
                        }
                        other_item.append((0, 0, move_data_dict))
                # if dry_items:
                #     picking_type = self.env['stock.picking.type'].search([('sequence_code', '=', 'INT TRF')])
                #
                #     hc_picking = {
                #         'picking_type_id': picking_type.id,
                #         'location_id': source_location.id,
                #         'location_dest_id': picking_type.default_location_dest_id.id,
                #         'move_ids_without_package': dry_items,
                #         'is_approval_required': True,
                #         'group_id': production.procurement_group_id.id,
                #         # 'state': 'draft'
                #         }
                #     picking_ids.append((0, 0,hc_picking))
                #     delivery_count = delivery_count+1
                if other_item:
                    picking_type = self.env['stock.picking.type'].search([('sequence_code', '=', 'PC')])

                    hc_picking_other = {
                        'picking_type_id': picking_type.id,
                        'location_id': picking_type.default_location_src_id.id,
                        'location_dest_id': picking_type.default_location_dest_id.id,
                        'move_ids_without_package': other_item,
                        # 'is_approval_required': False,
                        'group_id': production.procurement_group_id.id,
                        'state': 'draft'
                    }
                    picking_ids.append((0, 0, hc_picking_other))
                    delivery_count = delivery_count + 1
                production.write({
                    'picking_ids': picking_ids,
                    'delivery_count': delivery_count
                })
            # (production.move_raw_ids | production.move_finished_ids)._action_confirm(merge=False)
            (production.move_finished_ids)._action_confirm(merge=False)
            production.workorder_ids._action_confirm()
            production.delivery_count = delivery_count
        # run scheduler for moves forecasted to not have enough in stock
        self.move_raw_ids._trigger_scheduler()
        self.picking_ids.filtered(
            lambda p: p.state not in ['cancel', 'done']).action_confirm()
        # Force confirm state only for draft production not for more advanced state like
        # 'progress' (in case of backorders with some qty_producing)
        # self.picking_ids
        pickk = self.picking_ids.button_validate()
        print("self.picking_ids", self.picking_ids)
        for picking in self.picking_ids:
            for mov_line in picking.move_line_ids_without_package:
                mov_line.qty_done = mov_line.product_uom_qty
        # dddd
        if pickk.get('name') == 'Immediate Transfer?':
            back_order = self.env['stock.backorder.confirmation'].with_context(pickk['context']).process()
        self.filtered(lambda mo: mo.state == 'draft').state = 'confirmed'
        if self.move_raw_ids:
            for component in self.move_raw_ids:
                # fff
                for move_line in component.move_line_ids:
                    component_product = move_line.product_id
                    if component_product:
                        if not move_line.lot_id:
                            lot = self.env['stock.production.lot'].search(
                                [('product_id', '=', component_product.id),
                                 ('company_id', '=', move_line.company_id.id),
                                 ('product_qty', '>=', move_line.qty_done)], limit=1)

                            if lot:
                                move_line.lot_id = lot
                            # move_line.lot_id = self.env['stock.production.lot'].create({
                            #     'product_id': move_line.product_id.id,
                            #     'company_id': move_line.company_id.id,
                            #     'name': self.name
                            # })

        return True

    def button_mark_done(self):
        for rec in self:
            if rec.move_raw_ids:
                for component in rec.move_raw_ids:
                    print("sadsaj jjjjss", component.move_line_ids)
                    for move_line in component.move_line_ids:
                        print("dsfjsdkjfsd jdd", move_line, move_line.qty_done, move_line.lot_id)
                        component_product = move_line.product_id
                        if component_product:
                            if not move_line.lot_id:
                                print("uiss...ss", move_line, move_line.qty_done)
                                # stock_quant_j = self.env['stock.quant'].search(
                                #     [
                                #         ('product_id', '=', component_product.id),
                                #         ('location_id', '=', rec.location_src_id.id),
                                #         ('available_quantity', '>=', move_line.qty_done),
                                #         ('lot_id', '!=', False)], limit=1)
                                # print("duuuuuusiisis", stock_quant_j)
                                # if not stock_quant_j:
                                #     stock_quant_j = self.env['stock.quant'].search(
                                #         [
                                #             ('product_id', '=', component_product.id),
                                #             ('location_id', '=', rec.location_src_id.id),
                                #             ('available_quantity', '>=', 1),
                                #             ('lot_id', '!=', False)], limit=1)
                                # print("sdfdskjfskdljfs", stock_quant_j, )
                                # lot = stock_quant_j.lot_id.id


                                current_date = datetime.now()
                                # lots = self.env['stock.production.lot'].search(
                                #     [('product_id', '=', component_product.id),
                                #      ('company_id', '=', move_line.company_id.id),('expiration_date', '!=', False)
                                #      ('product_qty', '>=', move_line.qty_done),('expiration_date', '>=', current_date)])
                                # lot = self.get_expireing_lot(lots)
                                lot = self.env['stock.production.lot'].search(
                                    [('product_id', '=', component_product.id),
                                     ('company_id', '=', move_line.company_id.id),
                                     ('product_qty', '>=', move_line.qty_done),
                                     ],limit=1)
                                # lot = self.get_expireing_lot(lots)
                                if lot:
                                    move_line.lot_id = lot
                        move_line.qty_done = component.product_uom_qty
                component.quantity_done = component.product_uom_qty
        # eee
        res = super(MrpProduction, self).button_mark_done()
        return res

    # def get_expireing_lot(self, lots):


