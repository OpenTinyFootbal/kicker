from odoo import models, fields, api

import datetime
from dateutil import relativedelta

class ResPartner(models.Model):
    _inherit = 'res.partner'

    kicker_session_ids = fields.One2many('kicker.session', 'player_id', string='Kicker Sessions')
    wins = fields.Integer(compute='_compute_stats')
    losses = fields.Integer(compute='_compute_stats')
    kicker_player = fields.Boolean()
    main_kicker_id = fields.Many2one('kicker.kicker', 'Default Kicker')
    tagline = fields.Char()

    @api.depends('kicker_session_ids')
    def _compute_stats(self):
        data = self.env['kicker.session'].read_group([('player_id', 'in', self.ids)], fields=['player_id', 'won'], groupby=['player_id', 'won'], lazy=False)
        for partner in self:
            wins = list(filter(lambda d: d['player_id'][0] == partner.id and d['won'], data))
            partner.wins = wins and sum(list(map(lambda w: w['__count'], wins)))
            losses = list(filter(lambda d: d['player_id'][0] == partner.id and not d['won'], data))
            partner.losses = losses and sum(list(map(lambda l: l['__count'], losses)))

    def _get_usual_players(self):
        self.ensure_one()
        month_ago = datetime.datetime.now() - relativedelta.relativedelta(months=1)
        monthly_games = self.env['kicker.game'].search([('session_ids', 'in', self.kicker_session_ids.ids), ('create_date', '>', month_ago)])
        friend_sessions = self.env['kicker.session'].read_group(domain=[('game_id', 'in', monthly_games.ids), ('player_id', '!=', self.id)],groupby=['player_id'], fields=['player_id'])
        ordered_friend_ids = list(map(lambda f: f['player_id'][0], sorted(friend_sessions, key=lambda f: f['player_id_count'], reverse=True)))
        return self.browse(ordered_friend_ids)


    def _community_stats(self):
        usual = self._get_usual_players()
        rare = self.search([('kicker_player', '=', True), ('id', 'not in', usual.ids + self.ids)])
        return {
            'usual': usual.read(['id', 'name', 'tagline']),
            'rare': rare.read(['id', 'name', 'tagline']),
        }

    def _dashboard_stats(self):
        teammates = self._get_usual_players()
        nightmares = self.browse()
        data = {
            'name': self.name,
            'wins': self.wins,
            'losses': self.losses,
            'teammates': teammates.read(['id', 'name', 'tagline']),
            'nightmares': nightmares.read(['id', 'name', 'tagline']),
            'graph': [58, 69, 61, 85, 89]
        }
        return data
