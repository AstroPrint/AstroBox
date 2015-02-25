# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

# singleton
_instance = None

def variantManager():
	global _instance
	if _instance is None:
		_instance = VariantManager()
	return _instance

import os
import logging
import yaml

from octoprint.settings import settings

class VariantManager(object):	
	def __init__(self):
		self._settings = settings()
		self._variantFile = self._settings.get(['software', 'variantFile']) or "%s/variant.yaml" % os.path.dirname(__file__)
		self._logger = logging.getLogger(__name__)

		self.forceUpdateInfo = None
		self.data = {}

		if not os.path.isfile(self._variantFile):
			raise IOError("Variant File %s not found" % self._variantFile)

		else:
			with open(self._variantFile, "r") as f:
				self.data = yaml.safe_load(f)