install:
	echo "Installing Python dependencies..."
	pip install -r /AstroBox/requirements.txt
	
	echo "Disabling unnecessary services on startup..."
	update-rc.d isc-dhcp-server disable
	update-rc.d hostapd disable

	echo "Configuring haproxy"
	cp /etc/default/haproxy /etc/default/haproxy.bak
	sed -i /etc/default/haproxy -e "/ENABLED=/c ENABLED=1"
	mv /etc/haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg.bak
	cp /etc/haproxy/haproxy_astrobox.cfg /etc/haproxy/haproxy.cfg
	service haproxy restart

	echo "Configuring Hotspot..."
	cp /etc/default/hostapd /etc/default/hostapd.bak
	sed -i /etc/default/hostapd \
		-e '/DAEMON_CONF=/c DAEMON_CONF="/etc/hostapd/hostapd.conf"'

	echo "Configuring DHCP server for hotspot..."
	cp /etc/default/isc-dhcp-server /etc/default/isc-dhcp-server.bak
	sed -i /etc/default/isc-dhcp-server \
		-e "/INTERFACES=/c INTERFACES=wlan1"

	cp /etc/dhcp/dhcpd.conf /etc/dhcp/dhcp.conf.bak
		sed -i /etc/dhcp/dhcpd.conf \
    		-e 's/^option domain-name/#option domain-name/' \
    		-e 's/^option domain-name-servers/#option domain-name-servers/' \
    		-e 's/^default-lease-time/#default-lease-time/' \
    		-e 's/^max-lease-time/#max-lease-time/'

	sed -i /etc/dhcp/dhcpd.conf \
    	-e '/subnet 10.10.0.0 netmask 255.255.255.0/,+4 d'

#	cat <<EOF >> /etc/dhcp/dhcpd.conf
#	subnet 10.10.0.0 netmask 255.255.255.0 {
#        range 10.10.0.2 10.10.0.16;
#        option domain-name-servers 8.8.4.4, 208.67.222.222;
#        option routers 10.10.0.1;
#	}
#	EOF
