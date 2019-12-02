from odoo import models, fields, api, _
from odoo.exceptions import UserError

import datetime
from dateutil import relativedelta

class ResPartner(models.Model):
    _inherit = 'res.partner'

    kicker_session_ids = fields.One2many('kicker.session', 'player_id', string='Kicker Sessions')
    wins = fields.Integer(compute='_compute_stats', string='Total Wins')
    losses = fields.Integer(compute='_compute_stats', string='Total Losses')
    win_ratio = fields.Integer(compute='_compute_stats', string='Win Ratio')
    weekly_wins = fields.Integer(compute='_compute_stats', string='Weekly Wins')
    weekly_losses = fields.Integer(compute='_compute_stats', string='Weekly Losses')
    weekly_win_ratio = fields.Integer(compute='_compute_stats', string='Weekly Win Ratio')
    kicker_player = fields.Boolean()
    main_kicker_id = fields.Many2one('kicker.kicker', 'Default Kicker')
    tagline = fields.Char()

    @api.depends('kicker_session_ids')
    def _compute_stats(self):
        all_data = self.env['kicker.session'].read_group([('player_id', 'in', self.ids)], fields=['player_id', 'won'], groupby=['player_id', 'won'], lazy=False)
        weekly_data = self.env['kicker.session'].read_group([('player_id', 'in', self.ids), ('game_date', '>', datetime.datetime.now() - datetime.timedelta(days=7))], fields=['player_id', 'won'], groupby=['player_id', 'won'], lazy=False)
        for partner in self:
            wins = list(filter(lambda d: d['player_id'][0] == partner.id and d['won'], all_data))
            partner.wins = wins and sum(list(map(lambda w: w['__count'], wins)))
            losses = list(filter(lambda d: d['player_id'][0] == partner.id and not d['won'], all_data))
            partner.losses = losses and sum(list(map(lambda l: l['__count'], losses)))
            if not (partner.wins + partner.losses):
                partner.win_ratio = 0
            else:
                partner.win_ratio = 100*partner.wins/(partner.wins+partner.losses)
            weekly_wins = list(filter(lambda d: d['player_id'][0] == partner.id and d['won'], weekly_data))
            partner.weekly_wins = weekly_wins and sum(list(map(lambda w: w['__count'], weekly_wins)))
            weekly_losses = list(filter(lambda d: d['player_id'][0] == partner.id and not d['won'], weekly_data))
            partner.weekly_losses = weekly_losses and sum(list(map(lambda l: l['__count'], weekly_losses)))
            if not (partner.weekly_wins + partner.weekly_losses):
                partner.weekly_win_ratio = 0
            else:
                partner.weekly_win_ratio = 100*partner.weekly_wins/(partner.weekly_wins+partner.weekly_losses)

    def _get_usual_players(self):
        self.ensure_one()
        month_ago = datetime.datetime.now() - relativedelta.relativedelta(months=1)
        friends = self.env['kicker.stat'].read_group(domain=[('player_id', '=', self.id), ('date', '>', month_ago)],
                                                   fields=['teammate_id'], groupby=['teammate_id'])
        ordered_friends = list(map(lambda f: f['teammate_id'][0], sorted(friends, key=lambda f: f['teammate_id_count'], reverse=True)))
        return self.browse(ordered_friends)

    def _get_teammeates(self, period=False, limit=6):
        self.ensure_one()
        external_player = self.env.ref('kicker.anon_res_partner')
        domain = [('player_id', '=', self.id), ('won', '=', True), ('teammate_id', '!=', external_player.id)]
        if period=='month':
            month_ago = datetime.datetime.now() - relativedelta.relativedelta(months=1)
            domain.append([('date', '>', month_ago)])
        mates = self.env['kicker.stat'].read_group(domain=domain,
                                                   fields=['teammate_id'], groupby=['teammate_id'])
        ordered_mates = list(map(lambda f: f['teammate_id'][0], sorted(mates, key=lambda f: f['teammate_id_count'], reverse=True)))
        if limit:
            ordered_mates = ordered_mates[:limit]
        return self.browse(ordered_mates)
    
    def _get_opponents(self, period=False, limit=6):
        self.ensure_one()
        domain = [('player_id', '=', self.id), ('won', '=', False)]
        if period=='month':
            month_ago = datetime.datetime.now() - relativedelta.relativedelta(months=1)
            domain.append([('date', '>', month_ago)])
        # check for all stats where the opponent is in either opponent1_id or opponent2_id field
        opps1 = self.env['kicker.stat'].read_group(domain=domain,
                                                   fields=['opponent1_id'], groupby=['opponent1_id'])
        opps2 = self.env['kicker.stat'].read_group(domain=domain,
                                                   fields=['opponent2_id'], groupby=['opponent2_id'])
        # combine data (in case an opponent is present in both fields)
        all_opps = list(map(lambda o: o['opponent1_id'][0], opps1))
        all_opps += list(map(lambda o: o['opponent2_id'][0], opps2))
        all_opps = set(all_opps)
        vals = dict.fromkeys(all_opps, 0)
        for opp in all_opps:
            as_opp1 = list(filter(lambda o: o['opponent1_id'][0]==opp, opps1))
            if as_opp1:
                vals[opp] += as_opp1[0]['opponent1_id_count']
            as_opp2 = list(filter(lambda o: o['opponent2_id'][0]==opp, opps2))
            if as_opp2:
                vals[opp] += as_opp2[0]['opponent2_id_count']
        ordered_opps = sorted(vals.items(), key=lambda e: e[1], reverse=True)
        ordered_opps = [o[0] for o in ordered_opps]
        if limit:
            ordered_opps = ordered_opps[:limit]
        return self.browse(ordered_opps)

    def _community_stats(self):
        usual = self._get_usual_players()
        rare = self.search([('kicker_player', '=', True), ('id', 'not in', usual.ids + self.ids)], order='name asc')
        return {
            'usual': usual.read(['id', 'name', 'tagline']),
            'rare': rare.read(['id', 'name', 'tagline']),
        }

    def _compute_ratio(self, period=False):
        domain = [('player_id', '=', self.id)]
        if period=='month':
            month_ago = datetime.datetime.now() - relativedelta.relativedelta(months=1)
            domain.append([('date', '>', month_ago)])
        if period=='year':
            year_ago = datetime.datetime.now() - relativedelta.relativedelta(years=1)
            domain.append([('date', '>', year_ago)])
        stats = self.env['kicker.stat'].read_group(domain=domain,
                                                   fields=['date', 'won'], groupby=['date:month', 'won'], lazy=False)
        print(stats)
        stats = list(map(lambda w: (w['date:month'], w['date_count']), stats))
        print(stats)
        return stats

    def _dashboard_stats(self):
        self.ensure_one()
        teammates = self._get_teammeates()
        nightmares = self._get_opponents()
        data = {
            'name': self.name,
            'wins': self.wins,
            'losses': self.losses,
            'teammates': teammates.read(['id', 'name', 'tagline']),
            'nightmares': nightmares.read(['id', 'name', 'tagline']),
            'ratio': self.win_ratio,
            'weekly_wins': self.weekly_wins,
            'weekly_losses': self.weekly_losses,
            'weekly_win_ratio': self.weekly_win_ratio,
            'graph': [58, 69, 61, 85, 89]
        }
        return data

    @api.model
    def _get_rankings(self, period='month', metric='all'):
        if period=='week':
            date_limit = datetime.datetime.now() - relativedelta.relativedelta(weeks=1)
        elif period=='month':
            date_limit = datetime.datetime.now() - relativedelta.relativedelta(months=1)
        elif period=='year':
            date_limit = datetime.datetime.now() - relativedelta.relativedelta(years=1)
        domain = [('date', '>', date_limit), ('player_id.kicker_player', '=', True)]
        stats = self.env['kicker.stat'].read_group(domain=domain,
                                                   fields=['player_id', 'won'],
                                                   groupby=['player_id', 'won'],
                                                   lazy=False)
        # proably possible to get it in the read_group, i'm being lazy
        partner_ids = set(map(lambda s: s['player_id'][0], stats))
        names = self.browse(partner_ids).read(['name'])
        res = list()
        for pid in partner_ids:
            wins = list(filter(lambda s: {('player_id','=',pid),('won','=',True)}.issubset(s['__domain']),stats))
            wins = wins and wins[0]['__count'] or 0
            losses = list(filter(lambda s: {('player_id','=',pid),('won','=',False)}.issubset(s['__domain']),stats))
            losses = losses and losses[0]['__count'] or 0
            res.append({
                'id': pid,
                'name': list(filter(lambda s: s['id']==pid, names))[0]['name'],
                'won': wins,
                'lost': losses,
                'matches': wins + losses,
            })
        return res

    def write(self, vals):
        if 'kicker_player' in vals:
            if not self.user_has_groups('kicker.group_kicker_manager'):
                raise UserError(_("Only kicker managers can modify a player status"))
            if vals['kicker_player']:
                # erase email address upon validation
                vals['email'] = False

        return super().write(vals)

    def validate_kicker_signup(self):
        signup_template = self.env.ref('kicker.validate_signup')
        for partner in self:
            signup_template.send_mail(partner.id, force_send=True)
            partner.kicker_player = True
            user = partner.user_ids
            if len(user) > 1:
                raise UserError(_("There is more than one user for partner %s - make sure only one user is linked to this partner!") % partner.name)
            user.login = partner.name
