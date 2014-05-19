/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

 var PrintingView = Backbone.View.extend({
	el: '#printing-view',
    events: {
        'click .stop-print': 'stopPrint',
        'click .pause-print': 'togglePausePrint'
    },
    initialize: function(params) {
        this.listenTo(params.app.socketData, 'change:temps', this.onTempsChanged);
        this.listenTo(params.app.socketData, 'change:paused', this.onPausedChanged);
        this.listenTo(params.app.socketData, 'change:printing_progress', this.onProgressChanged);
    },
    onTempsChanged: function(s, value) {
        if (!this.$el.hasClass('hide')) {
            this.$el.find('.temperatures .nozzle .temp-target').text(value.extruder.target);
            this.$el.find('.temperatures .nozzle .temp-current').html(Math.round(value.extruder.actual)+'&deg;');
            this.$el.find('.temperatures .bed .temp-target').text(value.bed.target);
            this.$el.find('.temperatures .bed .temp-current').html(Math.round(value.bed.actual)+'&deg;');
        }
    },
    onProgressChanged: function(s, value) {
        //progress bar
        this.$el.find('.progress .meter').css('width', value.percent+'%');
        this.$el.find('.progress .progress-label').text(Math.round(value.percent)+'%');

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
        var pauseBtn = this.$el.find('button.pause-print')

        if (value) {
            pauseBtn.html('<i class="icon-play"></i> Resume Print');
        } else {
            pauseBtn.html('<i class="icon-pause"></i> Pause Print');
        }
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
        	cb(true);
        }).
        fail(function() {
        	noty({text: "There was an error starting the print", timeout: 3000});
        	cb(false);
        });
	},
    stopPrint: function() {
        this._jobCommand('cancel');
    },
    togglePausePrint: function() {
        this._jobCommand('pause');
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