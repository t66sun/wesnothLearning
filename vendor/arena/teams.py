"""Optional team extension. Absent team assignments preserve the frozen FFA profile."""


def validate(teams, players):
    if teams is None:
        return None
    if len(teams) != players or any(type(t) is not int or t < 1 for t in teams) or len(set(teams)) < 2:
        raise ValueError('teams need one positive integer per side and at least two teams')
    return list(teams)


def adjudicate(teams, survivors, faults):
    failed = {teams[int(s)-1] for s in faults}
    alive = {teams[s-1] for s in survivors} - failed
    winning_team = next(iter(alive)) if len(alive) == 1 else 0
    winners = [i for i, t in enumerate(teams, 1) if t == winning_team]
    return dict(teams=teams, winning_team=winning_team, winners=winners)
