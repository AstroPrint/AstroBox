# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from flask import jsonify, abort

from octoprint.server.api import api
from astroprint.boxrouter import boxrouterManager

@api.route("/boxrouter", methods=["POST"])
def connect_boxrouter():
	br = boxrouterManager()

	if br.boxrouter_connect():
		return jsonify()
	else:
		return abort(400)
