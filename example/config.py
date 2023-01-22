import json

class Config():
	_cfg = None

	def __init__(self, filename="example_config.json"):
		with open(filename, mode="r") as config_file:
			self._cfg = json.load(config_file)

	def get(self, prop, default=None, required=False):
		if prop not in self._cfg:
			if required:
				raise KeyError(f"{prop} must be specified in configuration file.")
			else:
				return default
		else:
			return self._cfg[prop]
