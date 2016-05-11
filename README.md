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

* Create an bootable image using the images from [AstroPrint](https://www.astroprint.com/downloads)

* Download the source code for getting your working copy:

  <pre>
    git clone https://github.com/AstroPrint/AstroBox.git
  </pre>

* If you intent to run from source, you also need to install:

  <pre>

    $ sudo apt-get install rubygems oracle-java8-jdk
    $ sudo gem install sass 
    $ pip install -r requirements.txt
  </pre>

* You can run the box from source like this:

  <pre>
    $ sudo service astrobox stop
    $ sudo python ./run --config /etc/astrobox/config.yaml --host 127.0.0.1
  </pre>