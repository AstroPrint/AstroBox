.SILENT:

all: upgrade-system install-deps copy-files set-configs

upgrade-system:
	echo "Adding Astroprint PPA"
	echo "deb http://ppa.astroprint.com stable main" > /etc/apt/sources.list.d/astroprint.ppa.list
	apt-get update
	apt-get dist-upgrade

install-deps:
	echo "Removing not needed packages"
	apt-get remove hostapd

	echo "Installing needed packages"
	apt-get install haproxy isc-dhcp-server nscd network-manager avahi-daemon ntp python-pip python-dev python-gobject python-apt python-dbus janus-astroprint libwebsocket gir1.2-gstreamer-1.0 gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-omx gcodeanaylizer-astroprint hostapd-astroprint
	pip install setuptools 
	pip install -r /AstroBox/requirements.txt

copy-files:
	cp -rf etc-astrobox/astrobox /etc
	cp -rf AstroBox /
	cp -rf pi /home
	cp -rf pi/tools/etc/dhcp/dhcpd.conf
	cp -rf pi/tools/etc/network/interfaces

set-configs:
	./setConfigs