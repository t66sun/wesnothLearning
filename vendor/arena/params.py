"""Frozen native-runtime competition profile, shared by both distributions."""
RULES_VERSION = 'wesnoth-1.18.8-native-v2'
WESNOTH_VERSION = '1.18.8'
PLAYERS = (2, 4, 8)
MAX_TURNS = 30
START_GOLD = 100
XP_MODIFIER = 70
ACTION_TIMEOUT = 1.0
FIRST_TIMEOUT = 10.0
OFFICIAL_TIMEOUT = 60.0
STARTUP_TIMEOUT = 120.0
MAX_ACTIONS = 2000
MAX_JOBS = 4
GAMES = 6
FACTIONS = ('Drakes', 'Knalgan Alliance', 'Loyalists', 'Northerners', 'Rebels', 'Undead')
LEADERS = ('Drake Flare', 'Dwarvish Steelclad', 'Lieutenant', 'Orcish Warrior', 'Elvish Captain', 'Dark Sorcerer')
RECRUITS = (
    'Drake Burner,Drake Clasher,Drake Fighter,Drake Glider,Saurian Augur,Saurian Skirmisher',
    'Dwarvish Fighter,Dwarvish Guardsman,Dwarvish Thunderer,Dwarvish Ulfserker,Footpad,Gryphon Rider,Poacher,Thief',
    'Bowman,Cavalryman,Fencer,Heavy Infantryman,Horseman,Mage,Merman Fighter,Spearman',
    'Goblin Spearman,Naga Fighter,Orcish Archer,Orcish Assassin,Orcish Grunt,Troll Whelp,Wolf Rider',
    'Elvish Archer,Elvish Fighter,Elvish Scout,Elvish Shaman,Mage,Merman Hunter,Wose',
    'Dark Adept,Ghost,Ghoul,Skeleton,Skeleton Archer,Vampire Bat,Walking Corpse',
)
