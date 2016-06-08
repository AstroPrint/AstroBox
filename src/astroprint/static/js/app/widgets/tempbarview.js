/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
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
        'touchstart .temp-target span.label': 'onTouchStart',
        'mousedown .temp-target span.label': 'onTouchStart',
        'touchmove': 'onTouchMove',
        'mousemove': 'onTouchMove',
        'touchend .temp-target': 'onTouchEnd',
        'mouseup .temp-target': 'onTouchEnd',
        'mouseout .temp-target': 'onTouchEnd',
        'click .temp-target a.temp-edit': 'onEditClicked',
        'change .temp-target input': 'onTempFieldChanged',
        'blur .temp-target input': 'onTempFieldBlur'
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

            var currentTemp = parseInt(this.$el.find('.temp-target span.label').text())

            if (!isNaN(currentTemp)) {
                this.setHandle(Math.min(currentTemp, value));
            }
        }
    },
    onTouchStart: function(e) {
        e.preventDefault();
        e.stopPropagation();

        this.dragging = true;
        $(e.currentTarget).closest('.temp-target').addClass('moving');
    },
    onTouchEnd: function(e) {
        e.preventDefault();

       $(e.currentTarget).removeClass('moving');

        this._sendToolCommand('target', this.type, this.$el.find('.temp-target span.label').text());

        this.dragging = false;
    },
    onEditClicked: function(e) {
        e.preventDefault();
        e.stopPropagation();

        var target = $(e.currentTarget);
        var container = target.closest('.temp-target');
        var label = container.find('span.label');
        var input = container.find('input');

        label.addClass('hide');
        input.removeClass('hide');
        input.val(label.text());
        setTimeout(function(){input.focus().select()},100);
    },
    onTempFieldChanged: function(e) {
        var input = $(e.target);
        var value = input.val();

        if (value != this.lastSent && !isNaN(value) ) {
            value = Math.min(Math.max(value, this.scale[0]), this.scale[1]);
            this._sendToolCommand('target', this.type, value);
            input.blur();

            this.setHandle(value);
        }
    },
    onTempFieldBlur: function(e)
    {
        var input = $(e.target);

        input.addClass('hide');
        input.closest('.temp-target').find('span.label').removeClass('hide');
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

        if (isNaN(actual)) {
            actual = null;
        }

        if (isNaN(target)) {
            target = null;
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
