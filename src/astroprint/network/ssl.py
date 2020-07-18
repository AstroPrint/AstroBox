# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os

from  distutils.dir_util import mkpath

from octoprint.settings import settings

from astroprint.software import softwareManager

#SSL_CERT_PATH = '/boot/.astrobox/ssl/cert.pem'
SSL_CERT_PATH = '/Users/arroyo/.astrobox/ssl/cert.pem'

class SslManager(object):
	def __init__(self):
		self._settings = settings()

	def isSslActive(self):
		return os.path.isfile(SSL_CERT_PATH)

	def disable(self):
		if self.isSslActive():
			dirname = os.path.dirname(SSL_CERT_PATH)
			os.rename(dirname, dirname.replace('ssl', 'ssl_disabled'))
			softwareManager().restartServer()

	def enable(self):
		if not self.isSslActive():
			disabledPath = SSL_CERT_PATH.replace('ssl', 'ssl_disabled')
			if os.path.isfile(disabledPath):
				os.rename(os.path.dirname(disabledPath), os.path.dirname(SSL_CERT_PATH))

			else:
				from astroprint.cloud import astroprintCloud

				astroprint = astroprintCloud()
				cert = astroprint.get_local_certificate()
				if cert is not None:
					mkpath(os.path.dirname(SSL_CERT_PATH))
					with open(SSL_CERT_PATH, 'w') as f:
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
