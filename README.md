AstroBox Software - Orange Pi Zero Port
=================

The AstroBox software provides a responsive web interface for controlling a 3D printer (RepRap, Ultimaker, ...) and connecting to the AstroPrint cloud for easy 3D Printing anywhere. It is Free Software and released under the [GNU Affero General Public License V3](http://www.gnu.org/licenses/agpl.html).

This project started as a branched fork of [AstroBox](https://github.com/AstroPrint/AstroBox). Many thanks to Astroprint Team and all the great contributors there that made the AstroBox software possible.

Its website can be found at [astroprint.com](https://www.astroprint.com).

Reporting bugs
--------------

The Orange Pi Zero issue tracker can be found [on Github](https://github.com/moracabanas/AstroBox/issues).


Installation instructions
-------



* Download a Armbian 5.30 bootable image using the image from [Armbian](https://dl.armbian.com/orangepizero/Ubuntu_xenial_default.7z)

* Make a SD card bootable with Etcher [Etcher](https://etcher.io/)

* Connect your Orange Pi Zero to your PC, wait a minute. A new device will be found just look for the COM port and take note. (On Windows you can use Device Manager).

* Use your preferred SSH App to access the found COM port which gives you instant command line to your Orange Pi. I Use [Putty](https://www.chiark.greenend.org.uk/~sgtatham/putty/latest.html) on Windows.


* Download the source code to your user directory (or any other place)

  <pre>
    git clone https://github.com/moracabanas/AstroBox.git
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
