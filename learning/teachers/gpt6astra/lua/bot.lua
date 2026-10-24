local players=#wesnoth.sides
local strategy=players==2 and 'duel' or players==4 and 'four' or 'eight'
return wesnoth.dofile('~add-ons/gpt6astra/lua/'..strategy..'.lua')
