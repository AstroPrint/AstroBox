# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os

from  distutils.dir_util import mkpath

from octoprint.settings import settings
from astroprint.ro_config import roConfig

from astroprint.software import softwareManager

class SslManager(object):
	def __init__(self):
		self._settings = settings()
		self.sslCertPath = roConfig('network.ssl.certPath')

	def isSslActive(self):
		return os.path.isfile(self.sslCertPath)

	def disable(self):
		if self.isSslActive():
			dirname = os.path.dirname(self.sslCertPath)
			os.rename(dirname, dirname.replace('ssl', 'ssl_disabled'))
			softwareManager().restartServer()

	def enable(self):
		if not self.isSslActive():
			disabledPath = self.sslCertPath.replace('ssl', 'ssl_disabled')
			if os.path.isfile(disabledPath):
				os.rename(os.path.dirname(disabledPath), os.path.dirname(self.sslCertPath))

			else:
				from astroprint.cloud import astroprintCloud

				astroprint = astroprintCloud()
				cert = astroprint.get_local_certificate()
				if cert is not None:
					mkpath(os.path.dirname(self.sslCertPath))
					with open(self.sslCertPath, 'w') as f:
						f.write(cert)
				else:
					raise NoCertException()

			softwareManager().restartServer()

	def setDomain(self, domain):
		self._settings.set(['network', 'ssl', 'domain'], domain)
		self._settings.save()

	def getDomain(self):
		return self._settings.get(['network', 'ssl', 'domain'])

# Exceptions

class NoCertException(Exception):
	pass
