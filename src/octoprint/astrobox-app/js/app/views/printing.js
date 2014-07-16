/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

 var tempBarHorizontalView = Backbone.View.extend({
    containerDimensions: null,
    scale: null,
    type: null,
    dragging: false,
    events: {
        'touchstart .temp-target': 'onTouchStart',
        'mousedown .temp-target': 'onTouchStart',
        'touchmove .temp-target': 'onTouchMove',
        'mousemove .temp-target': 'onTouchMove',
        'touchend .temp-target': 'onTouchEnd',
        'mouseup .temp-target': 'onTouchEnd',
        'mouseout': 'onTouchEnd',
        'click': 'onClicked'
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
    setHandle: function(value) {
        if (!this.dragging) {
            var position = this._temp2px(value);
            var handle = this.$el.find('.temp-target');

            handle.text(value);
            handle.css({transition: 'left 0.5s'});
            handle.css({left: position + 'px'});
            setTimeout(function() {
                handle.css({transition: ''});
            }, 800);
        }
    },
    onTouchStart: function(e) {
        e.preventDefault();
        this.dragging = true;
        $(e.target).addClass('moving');
    },
    onTouchMove: function(e) {
        if (this.dragging) {
            e.preventDefault();

            var target = $(e.target);

            if (e.type == 'mousemove') {
                var pageX = e.originalEvent.pageX;
            } else {
                var pageX = e.originalEvent.changedTouches[0].clientX;
            }

            var newLeft = pageX - this.containerDimensions.left - target.innerWidth()/2.0;
            newLeft = Math.min(Math.max(newLeft, this.containerDimensions.minLeft), this.containerDimensions.maxLeft );

            target.text(this._px2temp(newLeft));
            target.css({left: newLeft+'px'});
        }
    },
    onTouchEnd: function(e) {
        e.preventDefault();

        $(e.target).removeClass('moving');

        this._sendToolCommand('target', this.type, this.$el.find('.temp-target').text());

        this.dragging = false;
    },
    onClicked: function(e) {
        e.preventDefault();

        var target = this.$el.find('.temp-target');

        var newLeft = e.pageX - this.containerDimensions.left - target.innerWidth()/2.0;
        newLeft = Math.min(Math.max(newLeft, this.containerDimensions.minLeft), this.containerDimensions.maxLeft);

        var temp = this._px2temp(newLeft);

        this.setHandle(temp);
        this._sendToolCommand('target', this.type, temp);
    },
    onResize: function() {
        var container = this.$el;
        var handle = container.find('.temp-target');
        var currentLabel = container.find('.temp-current');
        var label = container.find('label');

        var width = container.width();
        var maxLeft = currentLabel.position().left - handle.innerWidth()*1.7;
        var minLeft = label.innerWidth();

        this.containerDimensions = {
            left: container.offset().left,
            width: width,
            maxLeft: maxLeft,
            minLeft: minLeft,
            px4degree: (maxLeft - minLeft) / (this.scale[1] - this.scale[0])
        };
    },
    setTemps: function(actual, target) {
        var handleWidth = this.$el.find('.temp-target').innerWidth();

        this.setHandle(Math.min(Math.round(target), this.scale[1]));
        this.$el.find('.temp-current').html(Math.round(actual)+'&deg;');
        this.$el.find('.temp-curret-line').css({left: ( this._temp2px(actual) + handleWidth/2.0 )+'px'});
    },
    _temp2px: function(temp) {
        var px = temp * this.containerDimensions.px4degree;

        return this.containerDimensions.minLeft + px;
    },
    _px2temp: function(px) {
        return Math.round( ( (px - this.containerDimensions.minLeft) / this.containerDimensions.px4degree ) );
    },
    _sendToolCommand: function(command, type, temp, successCb, errorCb) {
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
    }
});

 var PrintingView = Backbone.View.extend({
	el: '#printing-view',
    events: {
        'click button.stop-print': 'stopPrint',
        'click button.pause-print': 'togglePausePrint',
        'click button.controls': 'showControlPage'
    },
    nozzleBar: null,
    bedBar: null,
    initialize: function(params) {
        this.nozzleBar = new tempBarHorizontalView({
            scale: [0, 280],
            el: this.$el.find('.temp-bar.nozzle'),
            type: 'tool0' 
        });
        this.bedBar = new tempBarHorizontalView({
            scale: [0, 120],
            el: this.$el.find('.temp-bar.bed'),
            type: 'bed' 
        });

        this.listenTo(params.app.socketData, 'change:temps', this.onTempsChanged);
        this.listenTo(params.app.socketData, 'change:paused', this.onPausedChanged);
        this.listenTo(params.app.socketData, 'change:printing_progress', this.onProgressChanged);
    },
    onTempsChanged: function(s, value) {
        if (!this.$el.hasClass('hide')) {
            this.nozzleBar.setTemps(value.extruder.actual, value.extruder.target);
            this.bedBar.setTemps(value.bed.actual, value.bed.target);

            /*this.$el.find('.temperatures .nozzle .temp-target').text(value.extruder.target);
            this.$el.find('.temperatures .nozzle .temp-current').html(Math.round(value.extruder.actual)+'&deg;');
            this.$el.find('.temperatures .bed .temp-target').text(value.bed.target);
            this.$el.find('.temperatures .bed .temp-current').html(Math.round(value.bed.actual)+'&deg;');*/
        }
    },
    onProgressChanged: function(s, value) {
        var filenameNode = this.$el.find('.progress .filename');

        if (filenameNode.text() != value.filename) {
            filenameNode.text(value.filename);
        }

        //progress bar
        this.$el.find('.progress .meter').css('width', value.percent+'%');
        this.$el.find('.progress .progress-label').text(Math.floor(value.percent)+'%');

        //time
        var time = this._formatTime(value.time_left);
        this.$el.find('.estimated-hours').text(time[0]);
        this.$el.find('.estimated-minutes').text(time[1]);
        this.$el.find('.estimated-seconds').text(time[2]);

        //layers
        this.$el.find('.current-layer').text(value.current_layer);
        this.$el.find('.layer-count').text(value.layer_count);

        //heating up
        if (value.heating_up) {
            this.$el.find('.print-info').addClass("heating-up");
        } else {
            this.$el.find('.print-info').removeClass("heating-up");
        }
    },
    _formatTime: function(seconds) {
        var sec_num = parseInt(seconds, 10); // don't forget the second param
        var hours   = Math.floor(sec_num / 3600);
        var minutes = Math.floor((sec_num - (hours * 3600)) / 60);
        var seconds = sec_num - (hours * 3600) - (minutes * 60);

        if (hours   < 10) {hours   = "0"+hours;}
        if (minutes < 10) {minutes = "0"+minutes;}
        if (seconds < 10) {seconds = "0"+seconds;}
        return [hours, minutes, seconds];
    },
    onPausedChanged: function(s, value) {
        var pauseBtn = this.$el.find('button.pause-print');
        var controlBtn = this.$el.find('button.controls');

        if (value) {
            pauseBtn.html('<i class="icon-play"></i> Resume Print');
            controlBtn.show();
        } else {
            pauseBtn.html('<i class="icon-pause"></i> Pause Print');
            controlBtn.hide();
        }
    },
    show: function() {
        this.nozzleBar.onResize();
        this.bedBar.onResize();
    },
	startPrint: function(filename, cb) {
        var self = this;

        $.ajax({
            url: '/api/files/local/'+filename,
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify({command: "select", print: true})
        }).
        done(function() {
            self.$el.find('.progress .filename').text(filename);
            if (cb) {
        	   cb(true);
            }
        }).
        fail(function() {
        	noty({text: "There was an error starting the print", timeout: 3000});
            if (cb) {
        	   cb(false);
            }
        });
	},
    stopPrint: function() {
        this._jobCommand('cancel');
    },
    togglePausePrint: function() {
        this._jobCommand('pause');
    },
    showControlPage: function() {
        app.menuSelected('control');
    },
    _jobCommand: function(command) {
        $.ajax({
            url: API_BASEURL + "job",
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify({command: command})
        });
    }
});