"""Format definitions and team credit shared by schedules, training and reports."""
FORMATS = ('duel', 'ffa4', 'team2v2')
PLAYERS = dict(duel=2, ffa4=4, team2v2=4)
TEAM2V2 = [1, 2, 1, 2]


def infer_format(result):
    if result.get('teams'):
        if sorted(result['teams'].count(t) for t in set(result['teams'])) == [2, 2]:
            return 'team2v2'
        raise ValueError('training supports teams of 2v2')
    players=len(result['bots'])
    return {2: 'duel', 4: 'ffa4'}.get(players,'compat'+str(players))


def record_format(record):
    name = record.get('format')
    if name not in FORMATS: raise ValueError('sample requires an explicit supported format')
    return name
