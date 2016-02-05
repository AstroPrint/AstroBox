AstroBox Software
=================

The AstroBox software provides a responsive web interface for controlling a 3D printer (RepRap, Ultimaker, ...) and connecting to the AstroPrint cloud for easy 3D Printing anywhere. It is Free Software and released under the [GNU Affero General Public License V3](http://www.gnu.org/licenses/agpl.html).

This project started as a fork of [OctoPrint](http://octoprint.org). Many thanks to Gina and all the great contributors there that made the AstroBox software possible.

Its website can be found at [astroprint.com](https://www.astroprint.com).

Reporting bugs
--------------

Our issue tracker can be found [on Github](https://github.com/3dagogo/astrobox/issues).


Installation instructions
-------

### Ubuntu

* Download the source code for getting your working copy:

  <pre>
  git clone https://github.com/AstroPrint/AstroBox.git
  </pre>

* Execute the next line:

  <pre>
  sudo apt-get install haproxy isc-dhcp-server nscd network-manager avahi-daemon ntp python-pip python-dev python-gobject python-apt python-numpy python-opencv
  </pre>
  
* Edit the file %Astrobox location%/local/config.yalm; this file must contains this information:
  <pre>
  cloudSlicer:
    apiHost: http://api.astroprint.dev
    boxrouter: ws://boxrouter.astroprint.dev:8085
    loggedUser: rafa@astroprint.com
  network:
    manager: MacDev
  server:
    firstRun: false
  </pre>

* In %Astrobox location%, run this command:

  <pre>
    pip install -r requirements.txt
  </pre>