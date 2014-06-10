/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

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
                    if (data.serial.baudrateOptions && data.serial.baudrate) {
                        var baudList = this.$el.find('#settings-baudrate');
                        _.each(data.serial.baudrateOptions, function(element){
                            baudList.append('<option val="'+element+'">'+element+'</option>');
                        });
                        baudList.val(data.serial.baudrate);
                    }

                    if (data.serial.portOptions && data.serial.port) {
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
    events: {
        'click button.upgrade': 'upgradeClicked',
        'click .loading-button.hotspot button': 'hotspotClicked',
        'click .loading-button.connect button': 'connectClicked'
    },
    upgradeClicked: function() {
        alert('upgrading');
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
                    alert('hotspot is not configured on this box');
                } else {
                    alert('The system is now creating a hotspot. Search and connect to it');
                    window.close();
                }
            },
            error: function() {
                console.error('failed to open hotspot');
            },
            complete: function() {
                el.removeClass('loading');
            }
        });
    },
    connectClicked: function(e) {
        var el = $(e.target).closest('.loading-button');

        el.addClass('loading');

        var data = {
            "action": "connect-internet"
        }

        $.ajax({
            url: API_BASEURL + "system",
            type: "POST",
            data: data,
            success: function(data, code, xhr) {
                if (xhr.status == 204) {
                    alert('connect-internet is not configured on this box');
                } else {
                    alert('The system has closed the hotspot. Connect to the same network as AstroBox.');
                    window.close();
                }
            },
            error: function() {
                console.error('failed to connect to the internet');
            },
            complete: function() {
                el.removeClass('loading');
            }
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