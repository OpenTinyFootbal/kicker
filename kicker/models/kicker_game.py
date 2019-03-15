import odoo
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import datetime
from dateutil.relativedelta import relativedelta
import random

class KickerGame(models.Model):
    _name = 'kicker.game'
    _description = 'Kicker Game'
    _order = 'create_date DESC'

    name = fields.Char(compute='_compute_name')
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    kicker_id = fields.Many2one('kicker.kicker', string='Kicker', ondelete='restrict', index=True)
    winning_team = fields.Selection([('team_1', 'Team 1'), ('team_2', 'Team 2')], compute='_compute_winning_team', store=True)
    score_1 = fields.Integer(string="Team 1 Score", required=True)
    score_2 = fields.Integer(string="Team 2 Score", required=True)
    session_ids = fields.One2many('kicker.session', 'game_id', string='Sessions')
    
    @api.depends('score_1', 'score_2')
    def _compute_winning_team(self):
        for game in self:
            game.winning_team = 'team_1' if game.score_1 > game.score_2 else 'team_2'
    
    @api.depends('score_1', 'score_2', 'session_ids')
    def _compute_name(self):
        for game in self:
            game.name = '@'.join([str(game.date), game.kicker_id.name])
    
#    @api.constrains('session_ids')
#    def _validate_session(self):
#        for game in self:
#            if len(game.session_ids != 4):
#                raise ValidationError(_('There must be 4 players per game'))

    @api.model
    def _generate_demo_data(self, amount=100):
        seconds_in_year = 365*24*60*60
        vals = list()
        kickers = self.env['kicker.kicker'].search([])
        for i in range(amount):
            players = self.env['res.partner'].search([('kicker_player', '=', True)])
            player_ids = random.sample(players.ids, 4)
            date = datetime.datetime.now() - datetime.timedelta(seconds=random.randrange(0,seconds_in_year))
            vals.append({
                'date': date,
                'kicker_id': kickers[random.randrange(0, len(kickers))].id,
                'score_1': 11,
                'score_2': 11 - random.randrange(2, 11),
                'session_ids': [
                    (0, False, {'team': 'team_1', 'player_id': player_ids[1]}),
                    (0, False, {'team': 'team_2', 'player_id': player_ids[2]}),
                    (0, False, {'team': 'team_2', 'player_id': player_ids[3]}),
                    (0, False, {'team': 'team_1', 'player_id': player_ids[0]}),
                ]
            })
        self.create(vals)

class KickerSession(models.Model):
    _name = 'kicker.session'
    _description = 'Kicker Session'

    game_id = fields.Many2one('kicker.game', required=True, index=True)
    won = fields.Boolean(compute='_compute_won', store=True)
    team = fields.Selection([('team_1', 'Team 1'), ('team_2', 'Team 2')], required=True)
    player_id = fields.Many2one('res.partner', string='Player', index=True,
        domain="[('kicker_player', '=', True)]")
    game_date = fields.Datetime(related='game_id.date', store=True)

    @api.depends('game_id', 'game_id.winning_team')
    def _compute_won(self):
        for session in self:
            session.won = session.team == session.game_id.winning_team
