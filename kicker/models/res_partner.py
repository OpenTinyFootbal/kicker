from odoo import models, fields, api, _

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
        friends = self.env['kicker.stat'].read_group(domain=[('player_id', '=', self.id), ('date', '>', month_ago)],
                                                   fields=['teammate_id'], groupby=['teammate_id'])
        ordered_friends = list(map(lambda f: f['teammate_id'][0], sorted(friends, key=lambda f: f['teammate_id_count'], reverse=True)))
        return self.browse(ordered_friends)

    def _get_teammeates(self, period=False, limit=6):
        self.ensure_one()
        domain = [('player_id', '=', self.id), ('won', '=', True)]
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
        teammates = self._get_teammeates()
        nightmares = self._get_opponents()
        data = {
            'name': self.name,
            'wins': self.wins,
            'losses': self.losses,
            'teammates': teammates.read(['id', 'name', 'tagline']),
            'nightmares': nightmares.read(['id', 'name', 'tagline']),
            'ratio': 75,
            'graph': [58, 69, 61, 85, 89]
        }
        return data

    @api.model
    def _get_rankings(self, period='month'):
        domain = [('won', '=', True)]
        if period=='month':
            month_ago = datetime.datetime.now() - relativedelta.relativedelta(months=1)
            domain.append(('date', '>', month_ago))
        if period=='year':
            year_ago = datetime.datetime.now() - relativedelta.relativedelta(years=1)
            domain.append(('date', '>', year_ago))
        stats = self.env['kicker.stat'].read_group(domain=domain,
                                                   fields=['player_id'], groupby=['player_id'])
        stats = map(lambda s: (s['player_id'][0], s['player_id_count']), stats)
        ordered_stats = sorted(stats, key=lambda s: s[1], reverse=True)
        # proably possible to get it in the read_group, i'm being lazy
        partner_ids = list(map(lambda s: s[0], ordered_stats))
        partner_names = dict.fromkeys(partner_ids)
        names = self.browse(partner_ids).read(['name'])
        for pid in partner_ids:
            partner_names[pid] = list(filter(lambda s: s['id']==pid, names))[0]['name']
        res = list()
        for rank, stat in enumerate(ordered_stats):
            res.append({
                'id': stat[0],
                'rank': rank,
                'name': partner_names[stat[0]],
                'count': stat[1],
            })
        return {
            'players': res,
            'label': _("Won Matches")
        }
