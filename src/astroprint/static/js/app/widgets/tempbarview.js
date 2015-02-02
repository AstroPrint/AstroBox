/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var TempBarView = Backbone.View.extend({
    containerDimensions: null,
    scale: null,
    type: null,
    dragging: false,
    lastSent: null,
    lastSentTimestamp: null,
    waitAfterSent: 2000, //During this time, ignore incoming target sets
    events: {
        'touchstart .temp-target': 'onTouchStart',
        'mousedown .temp-target': 'onTouchStart',
        'touchmove .temp-target': 'onTouchMove',
        'mousemove .temp-target': 'onTouchMove',
        'touchend .temp-target': 'onTouchEnd',
        'mouseup .temp-target': 'onTouchEnd',
        'mouseout .temp-target': 'onTouchEnd'
    },
    initialize: function(params) {
        this.scale = params.scale;
        this.type = params.type;
        $(window).bind("resize.app", _.bind(this.onResize, this));
    },
    remove: function() {
        $(window).unbind("resize.app");
        Backbone.View.prototype.remove.call(this);
    },
    turnOff: function(e) {
        this._sendToolCommand('target', this.type, 0);
        this.setHandle(0);
    },
    setMax: function(value) {
        if (this.scale[1] != value) {
            this.scale[1] = value;
            this.onResize();

            var currentTemp = parseInt(this.$el.find('.temp-target').text())

            if (!isNaN(currentTemp)) {
                this.setHandle(Math.min(currentTemp, value));
            }
        }
    },
    onTouchStart: function(e) {
        e.preventDefault();
        this.dragging = true;
        $(e.target).addClass('moving');
    },
    onTouchEnd: function(e) {
        e.preventDefault();

        $(e.target).removeClass('moving');

        this._sendToolCommand('target', this.type, this.$el.find('.temp-target').text());

        this.dragging = false;
    },
    _sendToolCommand: function(command, type, temp, successCb, errorCb) {
        if (temp == this.lastSent) return;

        var data = {
            command: command
        };

        var endpoint;
        if (type == "bed") {
            if ("target" == command) {
                data["target"] = parseInt(temp);
            } else if ("offset" == command) {
                data["offset"] = parseInt(temp);
            } else {
                return;
            }

            endpoint = "bed";
        } else {
            var group;
            if ("target" == command) {
                group = "targets";
            } else if ("offset" == command) {
                group = "offsets";
            } else {
                return;
            }
            data[group] = {};
            data[group][type] = parseInt(temp);

            endpoint = "tool";
        }

        $.ajax({
            url: API_BASEURL + "printer/" + endpoint,
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify(data),
            success: function() { if (successCb !== undefined) successCb(); },
            error: function() { if (errorCb !== undefined) errorCb(); }
        });

        this.lastSentTimestamp = new Date().getTime();
        this.lastSent = temp;
    },
    setTemps: function(actual, target) {
        var now = new Date().getTime();

        if (this.lastSent !== null && this.lastSentTimestamp > (now - this.waitAfterSent) ) {
            target = this.lastSent;
        }

        this.renderTemps(actual, target);
    },

    //Implement these in subclasses
    setHandle: function(value) {},
    onTouchMove: function(e) {},
    onClicked: function(e) {},
    onResize: function() {},
    renderTemps: function(actual, target) {},
    _temp2px: function(temp) {},
    _px2temp: function(px) {}
});