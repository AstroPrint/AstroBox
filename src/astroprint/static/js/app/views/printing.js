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
    lastSent: null,
    events: {
        'touchstart .temp-target': 'onTouchStart',
        'mousedown .temp-target': 'onTouchStart',
        'touchmove .temp-target': 'onTouchMove',
        'mousemove .temp-target': 'onTouchMove',
        'touchend .temp-target': 'onTouchEnd',
        'mouseup .temp-target': 'onTouchEnd',
        'mouseout .temp-target': 'onTouchEnd',
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
    _sendToolCommand: function(command, type, temp) {
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
            data: JSON.stringify(data)
        });

        this.lastSent = temp;
    }
});

 var PrintingView = Backbone.View.extend({
	el: '#printing-view',
    events: {
        'click button.stop-print': 'stopPrint',
        'click button.pause-print': 'togglePausePrint',
        'click button.controls': 'showControlPage',
        'show': 'show',
        'click button.take-pic': 'refreshPhoto',
        'click button.timelapse': 'timelapseClicked'
    },
    nozzleBar: null,
    bedBar: null,
    printing_progress: null,
    paused: null,
    photoSeq: 0,
    initialize: function() {
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

        this.listenTo(app.socketData, 'change:temps', this.onTempsChanged);
        this.listenTo(app.socketData, 'change:paused', this.onPausedChanged);
        this.listenTo(app.socketData, 'change:printing_progress', this.onProgressChanged);
    },
    render: function() 
    {
        //Progress data
        var filenameNode = this.$('.progress .filename');
        var cameraControls = this.$('.print-info .camera-controls');
        var imageNode = this.$('.print-info .camera-image');

        if (filenameNode.text() != this.printing_progress.filename) {
            filenameNode.text(this.printing_progress.filename);
        }

        if (this.printing_progress.camera_connected) {
            if (!cameraControls.is(":visible")) {
                cameraControls.show();
            }
        } else if (cameraControls.is(":visible") ) {
            cameraControls.hide();
        }

        if (imageNode.attr('src') != this.printing_progress.rendered_image) {
            imageNode.attr('src', this.printing_progress.rendered_image);
        }

        //progress bar
        this.$el.find('.progress .meter').css('width', this.printing_progress.percent+'%');
        this.$el.find('.progress .progress-label').text(Math.floor(this.printing_progress.percent)+'%');

        //time
        var time = this._formatTime(this.printing_progress.time_left);
        this.$el.find('.estimated-hours').text(time[0]);
        this.$el.find('.estimated-minutes').text(time[1]);
        this.$el.find('.estimated-seconds').text(time[2]);

        //layers
        this.$el.find('.current-layer').text(this.printing_progress.current_layer);
        if (this.printing_progress.layer_count) {
            this.$el.find('.layer-count').text(this.printing_progress.layer_count);
        }

        //heating up
        if (this.printing_progress.heating_up) {
            this.$el.addClass("heating-up");
        } else {
            this.$el.removeClass("heating-up");
        }

        //Paused state
        var pauseBtn = this.$el.find('button.pause-print');
        var controlBtn = this.$el.find('button.controls');

        if (this.paused) {
            pauseBtn.html('<i class="icon-play"></i> Resume Print');
            controlBtn.show();
        } else {
            pauseBtn.html('<i class="icon-pause"></i> Pause Print');
            controlBtn.hide();
        }
    },
    onTempsChanged: function(s, value) {
        if (!this.$el.hasClass('hide')) {
            this.nozzleBar.setTemps(value.extruder.actual, value.extruder.target);
            this.bedBar.setTemps(value.bed.actual, value.bed.target);
        }
    },
    onProgressChanged: function(s, value) {
        this.printing_progress = value;
        this.render();
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
        this.paused = value;
        this.render();
    },
    show: function() {
        this.nozzleBar.onResize();
        this.bedBar.onResize();
        this.printing_progress = app.socketData.get('printing_progress');
        this.paused = app.socketData.get('paused');
        this.render();
    },
    stopPrint: function() {
        this._jobCommand('cancel');
        app.router.navigate('', {replace:true, trigger: true});
        this.$el.find('.tab-bar .left-small').show();
    },
    togglePausePrint: function() {
        this._jobCommand('pause');
    },
    showControlPage: function() {
        app.router.navigate('control', {trigger: true, replace: true});
        this.$el.addClass('hide');
    },
    refreshPhoto: function(e) {
        var loadingBtn = $(e.target).closest('.loading-button');

        loadingBtn.addClass('loading');

        var text = Math.floor(this.printing_progress.percent)+'% - Layer '+(this.printing_progress.current_layer ? this.printing_progress.current_layer : '1')+( this.printing_progress.layer_count ? '/'+this.printing_progress.layer_count : '');
        var img = this.$('.print-info .camera-image');

        img.one('load', function() {
            loadingBtn.removeClass('loading');
        });
        img.one('error', function() {
            loadingBtn.removeClass('loading');
            $(this).attr('src', null);
        });
        img.attr('src', '/camera/snapshot?text='+encodeURIComponent(text)+'&seq='+this.photoSeq++);
    },
    timelapseClicked: function(e) {
        $.ajax({
            url: API_BASEURL + "camera/timelapse",
            type: "POST",
            dataType: "json",
            data: {
                freq: 15
            }
        });        
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