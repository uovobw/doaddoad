from doaddoad import DoadDoad
from Tweet import Tweet


def test_load_state():
	d = DoadDoad()
	d.load_state()
	# assert it's a dict
	assert type(d.state) == dict
	# assert it's structure
	assert type(d.state.keys()[0]) == int
	assert type(d.state.values()[0]) == Tweet
