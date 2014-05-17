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
            this.$el.find('#printing-bed-target').text(value.bed.target);
            this.$el.find('#printing-bed-current').text(value.bed.actual);
            this.$el.find('#printing-nozzle-target').text(value.extruder.target);
            this.$el.find('#printing-nozzle-current').text(value.extruder.actual);
        }
    },
    onProgressChanged: function(s, value) {
        this.$el.find('.progress .meter').css('width', value.percent+'%');

        var sec_num = parseInt(value.time_left, 10); // don't forget the second param
        var hours   = Math.floor(sec_num / 3600);
        var minutes = Math.floor((sec_num - (hours * 3600)) / 60);
        var seconds = sec_num - (hours * 3600) - (minutes * 60);

        if (hours   < 10) {hours   = "0"+hours;}
        if (minutes < 10) {minutes = "0"+minutes;}
        if (seconds < 10) {seconds = "0"+seconds;}
        var time    = hours+':'+minutes+':'+seconds;

        this.$el.find('#printing-time').text(time);
    },
    onPausedChanged: function(s, value) {
        var pauseBtn = this.$el.find('button.pause-print')

        if (value) {
            pauseBtn.text('RESUME PRINT');
        } else {
            pauseBtn.text('PAUSE PRINT');
        }
    },
	startPrint: function(filename, cb) {
        $.ajax({
            url: '/api/files/local/'+filename,
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify({command: "select", print: true})
        }).
        done(function() {
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