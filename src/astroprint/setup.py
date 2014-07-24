# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import re
import octoprint.server

from functools import wraps

from sys import platform

from flask import make_response, request

from octoprint.settings import settings
from octoprint.server import restricted_access, NO_CONTENT
from octoprint.server.api import api

def not_setup_only(func):
	"""
	If you decorate a view with this, it will ensure that the calls only run on
	first setup.
	"""
	@wraps(func)
	def decorated_view(*args, **kwargs):
		# if OctoPrint hasn't been set up yet, allow
		if settings().getBoolean(["server", "firstRun"]):
			return func(*args, **kwargs)
		else:
			return make_response("AstroBox is already setup", 403)
	return decorated_view

@api.route('/setup/name', methods=['POST'])
@not_setup_only
def save_name():
	name = request.values.get('name', None)

	if not name or not re.search(r"^[a-zA-Z0-9\-_]+$", name):
		return make_response('Invalid Name', 400)
	else:
		if platform == "linux" or platform == "linux2":
			return make_response('Not suported', 400)
		else:
			return NO_CONTENT