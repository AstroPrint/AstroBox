AstroBox Software
=================

The AstroBox software provides a responsive web interface for controlling a 3D printer (RepRap, Ultimaker, ...) and connecting to the AstroPrint cloud for easy 3D Printing anywhere. It is Free Software and released under the [GNU Affero General Public License V3](http://www.gnu.org/licenses/agpl.html).

This project started as a fork of [OctoPrint](http://octoprint.org). Many thanks to Gina and all the great contributors there that made the AstroBox software possible.

Its website can be found at [astroprint.com](https://www.astroprint.com).

Reporting bugs
--------------

Our issue tracker can be found [on Github](https://github.com/astroprint/astrobox/issues).


Installation instructions
-------



* Create an bootable image using the images from [AstroPrint](https://www.astroprint.com/downloads)

* Download the source code to get a working copy:

  <pre>
    git clone https://github.com/AstroPrint/AstroBox.git
  </pre>

Additional (to run from source):
-------
### Ubuntu

<pre>
  sudo apt-get install rubygems oracle-java8-jdk
</pre>
  
### Mac

<pre>
  gem install rubygems-update
</pre>
  Download and install oracle-java8-jdk from [here](http://www.oracle.com/technetwork/java/javase/downloads/jdk8-downloads-2133151.html).
### Ubuntu/Mac
<pre>
  $ sudo gem install sass 
  $ sudo pip install -r requirements.txt
</pre>

* You can run the box from source like this:

  <pre>
    $ sudo service astrobox stop
    $ sudo python ./run --config /etc/astrobox/config.yaml --host 127.0.0.1
  </pre>

Setting up the virtual printer
-------

The AstroBox Software comes with a handy virtual printer so that you can test without the need of a real 3D Printer attached. Here's how you can set it up

* Edit or create, the `printer-profile.yaml` file in your settings directory (by default `[AstroBox Directory]/local`). Change or add the line:
<pre>
  driver: virtual
</pre>

* Edit or create the `virtual-printer-settings.yaml` file in the same directory to guide your printing simulation. All values are in seconds. Here's a sample:

<pre>
  connection: 3.0
  heatingUp: 5.0
  printJob: 10.0
</pre>

* Restart AstroBox any time you make changes to these files
