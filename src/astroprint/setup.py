# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import re
import octoprint.server

from functools import wraps

from sys import platform

from flask import make_response, request, jsonify

from octoprint.settings import settings
from octoprint.server import restricted_access, NO_CONTENT
from octoprint.server.api import api
from octoprint.slicers.cloud.proven_to_print import ProvenToPrintSlicer

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

@api.route('/setup/internet', methods=['GET'])
@not_setup_only
def check_internet():
	return make_response('OK', 200)

@api.route('/setup/astroprint', methods=['GET'])
@not_setup_only
def get_astroprint_info():
	s = settings()

	email = s.get(['cloudSlicer', 'email'])

	if s.get(['cloudSlicer', "privateKey"]) and email:
		return jsonify(user=email)
	else:
		return jsonify(user=None)

@api.route('/setup/astroprint', methods=['DELETE'])
@not_setup_only
def astroprint_user():
	s = settings()

	s.set(['cloudSlicer', "privateKey"], None)
	s.set(['cloudSlicer', "email"], None)
	s.set(['cloudSlicer', "publicKey"], None)
	s.save()

	return make_response("OK", 200)


@api.route('/setup/astroprint', methods=['POST'])
@not_setup_only
def log_into_astroprint():
	email = request.values.get('email', None)
	password = request.values.get('password', None)

	if email and password:
		slicer = ProvenToPrintSlicer()

		private_key = slicer.get_private_key(email, password)

		if private_key:
			public_key = slicer.get_public_key(email, private_key)

			if public_key:
				s = settings()
				s.set(["cloudSlicer", "privateKey"], private_key)
				s.set(["cloudSlicer", "publicKey"], public_key)
				s.set(["cloudSlicer", "email"], email)
				#s.setBoolean(["server", "firstRun"], False)
				s.save()
				return make_response("OK", 200)

	return make_response('Invalid Credentials', 400)