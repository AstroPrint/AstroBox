# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2016 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging

def migrateSettings():
	from octoprint.settings import settings

	logger = logging.getLogger(__name__)
	logger.info('Checking for settings migrations...')
	migrationsDone = 0

	s = settings()

	#Migration to add the reboot action
	actions = s.get(['system', 'actions'])

	if 'reboot' not in [a["action"] for a in actions]:
		actions.append({
			'action': 'reboot',
			'command': 'reboot'
		})
		s.set(['system', 'actions'], actions, True)
		migrationsDone += 1

	# Migration for user plugins folder
	userPlugings = s.get(['folder', 'userPlugins'])
	uploads = s.get(['folder', 'uploads'])

	if uploads and not userPlugings:
		logger.info("Migrating config (user plugins folder)...")
		s.set(['folder','userPlugins'], uploads.replace('uploads', 'plugins'))
		migrationsDone += 1

	if migrationsDone > 0:
		s.save()

	logger.info('Performed %d settings migrations.' % migrationsDone)
