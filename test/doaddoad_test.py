from doaddoad import DoadDoad


def test_load_empty_state():
	d = DoadDoad()
	d.load_state()
	# assert it's a dict
	assert type(d.state) == dict
