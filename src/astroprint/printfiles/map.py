# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import itertools

from astroprint.printfiles.gcode import PrintFileManagerGcode
from astroprint.printfiles.x3g import PrintFileManagerX3g

printFileManagerMap = {
	PrintFileManagerGcode.name: PrintFileManagerGcode,
	PrintFileManagerX3g.name: PrintFileManagerX3g
}

#flatten the list of all supported extension
SUPPORTED_EXTENSIONS = list(itertools.chain(*[printFileManagerMap[c].SUPPORTED_EXTENSIONS for c in printFileManagerMap]))