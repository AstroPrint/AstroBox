/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var WiFiNetworkPasswordDialog = Backbone.View.extend({
    el: '#wifi-network-password-modal',
    events: {
        'click button.connect': 'connectClicked'
    },
    open: function(id, name) {
        this.$el.find('.network-id-field').val(id);
        this.$el.find('.name').text(name);
        this.$el.foundation('reveal', 'open');
        this.$el.find('.network-password-field').focus();
    },
    connectClicked: function(e) {
        e.preventDefault();

        console.log('Connecting to '+this.$el.find('form').serialize());
        this.$el.foundation('reveal', 'close');
    }
});

var WiFiNetworksDialog = Backbone.View.extend({
    el: '#wifi-network-list-modal',
    networksTemplate: _.template( $("#wifi-network-modal-row").html() ),
    passwordDlg: null,
    open: function(networks) {
        var content = this.$el.find('.modal-content');
        content.empty();

        content.html(this.networksTemplate({ 
            networks: networks
        }));

        content.find('button').bind('click', _.bind(this.networkSelected, this));

        this.$el.foundation('reveal', 'open');
    },
    networkSelected: function(e) {
        e.preventDefault();

        var button = $(e.target);

        if (!this.passwordDlg) {
            this.passwordDlg = new WiFiNetworkPasswordDialog();
        }

        this.passwordDlg.open(button.data('id'), button.data('name'));
    }
});

var SettingsPage = Backbone.View.extend({
    parent: null,
    initialize: function(params) {
        this.parent = params.parent;
    },
    show: function() {
        this.parent.$el.find('.settings-page').addClass('hide');
        this.$el.removeClass('hide');
    }
});

var PrinterConnectionView = SettingsPage.extend({
    el: '#printer-connection',
    settings: null,
    events: {
        'change #settings-baudrate': 'baudrateChanged',
        'change #settings-serial-port': 'portChanged'
    },
    show: function() {
        //Call Super
        SettingsPage.prototype.show.apply(this);

        if (!this.settings) {
            $.getJSON(API_BASEURL + 'settings', null, _.bind(function(data) {
                this.settings = data;
                if (data.serial) {
                    if (data.serial.baudrateOptions) {
                        var baudList = this.$el.find('#settings-baudrate');
                        _.each(data.serial.baudrateOptions, function(element){
                            baudList.append('<option val="'+element+'">'+element+'</option>');
                        });
                        baudList.val(data.serial.baudrate);
                    }

                    if (data.serial.portOptions) {
                        var portList = this.$el.find('#settings-serial-port');
                        _.each(data.serial.portOptions, function(element){
                            var option = $('<option val="'+element+'">'+element+'</option>');
                            if (data.serial.port == element) {
                                option.attr('selected', 1);
                            }
                            portList.append(option);
                        });
                    }
                } 
            }, this))
            .fail(function() {
                noty({text: "There was an error getting serial settings."});
            });
        }
    },
    baudrateChanged: function(e) {
        $.ajax({
            url: API_BASEURL + 'settings', 
            type: 'POST',
            contentType: 'application/json',
            dataType: 'json',
            data: JSON.stringify({serial: { baudrate: $(e.target).val() }})
        })
        .fail(function(){
            noty({text: "There was an error saving setting."});
        });
    },
    portChanged: function(e) {
        $.ajax({
            url: API_BASEURL + 'settings', 
            type: 'POST',
            contentType: 'application/json',
            dataType: 'json',
            data: JSON.stringify({serial: { port: $(e.target).val() }})
        })
        .fail(function(){
            noty({text: "There was an error saving setting."});
        });
    }
});

var InternetWifiView = SettingsPage.extend({
    el: '#internet-wifi',
    networksDlg: null,
    events: {
        'click .loading-button.hotspot button': 'hotspotClicked',
        'click .loading-button.connect button': 'connectClicked'
    },
    initialize: function(params) {
        SettingsPage.prototype.initialize.apply(this, arguments);

        this.networksDlg = new WiFiNetworksDialog();
    },
    hotspotClicked: function(e) {
        var el = $(e.target).closest('.loading-button');

        el.addClass('loading');

        var data = {
            "action": "hotspot"
        }

        $.ajax({
            url: API_BASEURL + "system",
            type: "POST",
            data: data,
            success: function(data, code, xhr) {
                if (xhr.status == 204) {
                    noty({text: 'hotspot is not configured on this box'});
                } else {
                    alert('The system is now creating a hotspot. Search and connect to it');
                    window.close();
                }
            },
            error: function() {
                noty({text: 'failed to open hotspot'});
            },
            complete: function() {
                el.removeClass('loading');
            }
        });
    },
    connectClicked: function(e) {
        var el = $(e.target).closest('.loading-button');

        el.addClass('loading');

        $.getJSON(
            API_BASEURL + "settings/wifi/networks",
            _.bind(function(data) {
                if (data.message) {
                    noty({text: data.message});
                } else if (data.networks) {
                    this.networksDlg.open(_.sortBy(_.uniq(_.sortBy(data.networks, function(el){return el.id}), true, function(el){return el.id}), function(el){return el.signal}));
                }
            }, this)
        ).
        fail(function(){
            noty({text: "There was an error retrieving networks."});
        }).
        complete(function(){
            el.removeClass('loading');
        });
    }
});

var SettingsMenu = Backbone.View.extend({
    el: '#settings-side-bar',
    subviews: null,
    events: {
        'click a.printer-connection': 'showPrinterConnection',
        'click a.internet-wifi': 'showInternetWifi'
    },
    initialize: function(params) {
        if (params.subviews) {
            this.subviews = params.subviews;
        }
    },
    _changeActive: function(e) {
        e.preventDefault();
        this.$el.find('li.active').removeClass('active');
        $(e.target).closest('li').addClass('active');
    },
    showPrinterConnection: function(e) {
        this._changeActive(e);
        this.subviews.printerConnection.show();
    },
    showInternetWifi: function(e) {
        this._changeActive(e);
        this.subviews.internetWifi.show();
    }
});

var SettingsView = Backbone.View.extend({
    el: '#settings-view',
    menu: null,
    events: {
        'show': 'onShow'
    },
    subviews: {
        printerConnection: null,
        internetWifi: null
    },
    initialize: function() {
        this.subviews.printerConnection = new PrinterConnectionView({parent: this});
        this.subviews.internetWifi = new InternetWifiView({parent: this});
        this.menu = new SettingsMenu({subviews: this.subviews});
    },
    onShow: function() {
        this.subviews.printerConnection.show();
    }
});
