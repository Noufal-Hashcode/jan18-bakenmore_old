# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from collections import defaultdict


class StockPicking(models.Model):
    _inherit = ['stock.picking']

    state = fields.Selection([
            ('draft', 'Draft'),
            ('waiting_for_approval', 'Waiting For Approval'),
            ('waiting', 'Waiting Another Operation'),
            ('confirmed', 'Waiting'),
            ('assigned', 'Ready'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ],string='Status', compute='_compute_state',copy=False, index=True,store=True, readonly=True, tracking=True,
            help=" * Draft: The transfer is not confirmed yet. Reservation doesn't apply.\n"
                 " * Waiting another operation: This transfer is waiting for another operation before being ready.\n"
                 " * Waiting: The transfer is waiting for the availability of some products.\n(a) The shipping policy is \"As soon as possible\": no product could be reserved.\n(b) The shipping policy is \"When all products are ready\": not all the products could be reserved.\n"
                 " * Ready: The transfer is ready to be processed.\n(a) The shipping policy is \"As soon as possible\": at least one product has been reserved.\n(b) The shipping policy is \"When all products are ready\": all product have been reserved.\n"
                 " * Done: The transfer has been processed.\n"
                 " * Cancelled: The transfer has been cancelled.")
    is_approval_required = fields.Boolean('Is Required Approval', help="authority to approve to transfer request")

    @api.depends('move_type', 'immediate_transfer', 'move_lines.state', 'move_lines.picking_id')
    def _compute_state(self):
        ''' State of a picking depends on the state of its related stock.move
        - Draft: only used for "planned pickings"
        - Waiting: if the picking is not ready to be sent so if
          - (a) no quantity could be reserved at all or if
          - (b) some quantities could be reserved and the shipping policy is "deliver all at once"
        - Waiting another move: if the picking is waiting for another move
        - Ready: if the picking is ready to be sent so if:
          - (a) all quantities are reserved or if
          - (b) some quantities could be reserved and the shipping policy is "as soon as possible"
        - Done: if the picking is done.
        - Cancelled: if the picking is cancelled
        '''
        picking_moves_state_map = defaultdict(dict)
        picking_move_lines = defaultdict(set)
        for move in self.env['stock.move'].search([('picking_id', 'in', self.ids)]):
            picking_id = move.picking_id
            move_state = move.state
            picking_moves_state_map[picking_id.id].update({
                'any_draft': picking_moves_state_map[picking_id.id].get('any_draft', False) or move_state == 'draft',
                'all_cancel': picking_moves_state_map[picking_id.id].get('all_cancel', True) and move_state == 'cancel',
                'all_cancel_done': picking_moves_state_map[picking_id.id].get('all_cancel_done',
                                                                              True) and move_state in (
                                   'cancel', 'done'),
                'all_done_are_scrapped': picking_moves_state_map[picking_id.id].get('all_done_are_scrapped', True) and (
                    move.scrapped if move_state == 'done' else True),
                'any_cancel_and_not_scrapped': picking_moves_state_map[picking_id.id].get('any_cancel_and_not_scrapped',
                                                                                          False) or (
                                                           move_state == 'cancel' and not move.scrapped),
            })
            picking_move_lines[picking_id.id].add(move.id)
        for picking in self:
            picking_id = (picking.ids and picking.ids[0]) or picking.id
            if not picking_moves_state_map[picking_id]:
                picking.state = 'draft'
            elif picking_moves_state_map[picking_id]['any_draft']:
                picking.state = 'draft'
            elif picking_moves_state_map[picking_id]['all_cancel']:
                picking.state = 'cancel'
            elif picking_moves_state_map[picking_id]['all_cancel_done']:
                if picking_moves_state_map[picking_id]['all_done_are_scrapped'] and picking_moves_state_map[picking_id][
                    'any_cancel_and_not_scrapped']:
                    picking.state = 'cancel'
                else:
                    picking.state = 'done'
            else:
                relevant_move_state = self.env['stock.move'].browse(
                    picking_move_lines[picking_id])._get_relevant_state_among_moves()
                if picking.immediate_transfer and relevant_move_state not in ('draft', 'cancel', 'done'):
                    picking.state = 'draft'
                elif relevant_move_state == 'partially_available':
                    picking.state = 'draft'
                else:
                    picking.state = relevant_move_state
            if picking.is_approval_required == True:
                picking.state = 'waiting_for_approval'

    def approve(self):
        self.state='assigned'

    # def action_confirm(self):
    #     for picking in self:
    #         picking._check_company()
    #         if picking.is_approval_required == True:
    #             picking.mapped('package_level_ids').filtered(lambda pl: pl.state == 'waiting_for_approval' and not pl.move_ids)._generate_moves()
    #         else:
    #             picking.mapped('package_level_ids').filtered(
    #                 lambda pl: pl.state == 'draft' and not pl.move_ids)._generate_moves()
    #
    #     # call `_action_confirm` on every draft move
    #         picking.mapped('move_lines') \
    #             .filtered(lambda move: move.state == 'draft') \
    #             ._action_confirm()
    #
    #         # run scheduler for moves forecasted to not have enough in stock
    #         self.mapped('move_lines').filtered(
    #             lambda move: move.state not in ('draft', 'cancel', 'done'))._trigger_scheduler()
    #         return True


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    picking_ids = fields.Many2many('stock.picking', compute='_compute_picking_ids', string='Picking associated to this manufacturing order',store=True)
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
                dry_items=[]
                other_item = []
                source_location = self.env['stock.location'].search([('name', '=', 'Dry Store')])
                for i in production.move_raw_ids:
                    if i.product_id.categ_id.name == 'Dry':
                        picking_type = self.env['stock.picking.type'].search([('sequence_code', '=', 'INT TRF')])
                        move_data_dict = {
                            'name': 'Mo Picking Move',
                            'location_id': picking_type.default_location_src_id.id,
                            'location_dest_id': picking_type.default_location_dest_id.id,
                            'product_id': i.product_id.id,
                            'product_uom': i.product_uom.id,
                            'product_uom_qty': i.product_uom_qty,
                        }
                        dry_items.append((0, 0,move_data_dict))
                    else:
                        picking_type = production.picking_type_id
                        move_data_dict = {
                            'name': 'Mo Picking Move',
                            'location_id': picking_type.default_location_src_id.id,
                            'location_dest_id': picking_type.default_location_dest_id.id,
                            'product_id': i.product_id.id,
                            'product_uom': i.product_uom.id,
                            'product_uom_qty': i.product_uom_qty,
                        }
                        other_item.append((0, 0, move_data_dict))
                if dry_items:
                    picking_type = self.env['stock.picking.type'].search([('sequence_code', '=', 'INT TRF')])

                    hc_picking = {
                        'picking_type_id': picking_type.id,
                        'location_id': source_location.id,
                        'location_dest_id': picking_type.default_location_dest_id.id,
                        'move_ids_without_package': dry_items,
                        'is_approval_required': True,
                        'group_id': production.procurement_group_id.id,
                        # 'state': 'draft'
                        }
                    picking_ids.append((0, 0,hc_picking))
                    delivery_count = delivery_count+1
                if other_item:
                    picking_type = production.picking_type_id

                    hc_picking_other = {
                        'picking_type_id': picking_type.id,
                        'location_id': picking_type.default_location_src_id.id,
                        'location_dest_id': picking_type.default_location_dest_id.id,
                        'move_ids_without_package': other_item,
                        'is_approval_required': False,
                        'group_id': production.procurement_group_id.id,
                        'state': 'draft'
                    }
                    picking_ids.append((0, 0,hc_picking_other))
                    delivery_count = delivery_count + 1
                production.write({
                    'picking_ids': picking_ids,
                    'delivery_count': delivery_count
                })
            # (production.move_raw_ids | production.move_finished_ids)._action_confirm(merge=False)
            (production.move_finished_ids)._action_confirm(merge=False)
            production.workorder_ids._action_confirm()
            production.delivery_count= delivery_count
        # run scheduler for moves forecasted to not have enough in stock
        self.move_raw_ids._trigger_scheduler()
        self.picking_ids.filtered(
            lambda p: p.state not in ['cancel', 'done']).action_confirm()
        # Force confirm state only for draft production not for more advanced state like
        # 'progress' (in case of backorders with some qty_producing)
        self.filtered(lambda mo: mo.state == 'draft').state = 'confirmed'
        return True




